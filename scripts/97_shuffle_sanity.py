#!/usr/bin/env python
"""Leakage sanity: shuffle the labels and confirm every finding collapses.

plan.md's Verification section asks for this against M2's lift. Taken literally
it is now vacuous -- M2 has no lift to collapse (D-43), so the test would pass
whatever the pipeline did. The informative version tests the two things the
project actually claims:

1. **The detector.** Ring size ranks rings at 2.85x the fraud baseline. Under
   shuffled client labels that must fall to 1.0x. If it does not, the ranking
   is picking up something about the label assignment rather than structure.

2. **The model harness.** Train M1 on globally shuffled labels and confirm test
   TPR at 1% FPR lands at chance (0.01). This is the check that matters for a
   null result: it proves the harness *can* report failure, so the null is
   evidence rather than a broken measurement.

The second is the one worth the compute. A pipeline that scores well on
shuffled labels is leaking; a pipeline that scores at chance has a working
evaluation, which is what licenses believing its other numbers.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from fds import paths, schema
from fds.cli import base_parser, record_run, resolve
from fds.evaluation import evaluate
from fds.features import categorical_columns, split_frames, tabular_feature_columns
from fds.ingest import load_base
from fds.links import LinkParams
from fds.models import train_seed_sweep
from fds.rings import detect_rings, score_rings
from fds.rng import rng_for
from fds.splits import Split

N_SHUFFLES = 8


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--recipe", default=None)
    parser.add_argument("--skip-model", action="store_true")
    args = parser.parse_args()
    cfg = resolve(args)
    recipe = args.recipe or cfg.uid.recipe_name
    link_columns = tuple(cfg.graph.link_types)
    params = LinkParams(
        min_degree=cfg.graph.hub_min_degree,
        max_degree=cfg.graph.hub_max_degree,
        min_weight=cfg.graph.min_edge_weight,
    )

    df = load_base(
        columns=[
            schema.KEY,
            schema.DAY,
            schema.TIME_RAW,
            schema.AMOUNT,
            schema.TARGET,
            *link_columns,
        ]
    ).merge(pd.read_parquet(paths.uid_map_path(recipe)), on=schema.KEY, validate="one_to_one")

    # --- 1. the detector -----------------------------------------------------
    print("-- detector: ring ranking under shuffled client labels --")
    membership, graph = detect_rings(df, link_columns=link_columns, params=params)
    rng = rng_for("shuffle_detector", cfg.seed)

    def lift(frame: pd.DataFrame) -> tuple[float, float]:
        """Size-controlled enrichment: observed fraud clients over expected.

        The obvious statistic -- the share of top-ranked rings holding two or
        more fraud clients -- is dominated by ring size: a ten-client ring
        clears that bar 60% of the time by chance alone. Under a shuffled null
        its baseline collapses faster than its numerator, so the ratio *rises*.
        That inversion is how this check found the broken metric (D-47).
        """
        rate = float(frame["n_fraud_clients"].sum() / frame["n_clients"].sum())
        top = frame.sort_values("n_clients", ascending=False).head(50)
        expected = float(top["n_clients"].sum()) * rate
        value = float(top["n_fraud_clients"].sum() / expected) if expected else float("nan")
        return value, rate

    real = score_rings(
        membership, graph, df, rng=rng, attribute_columns=link_columns, n_permutations=5
    )
    observed_lift, baseline = lift(real)
    print(f"  observed lift (ranked by size): {observed_lift:.3f}x  (baseline {baseline:.3f})")

    client_labels = df.groupby(schema.UID, observed=True)[schema.TARGET].max()
    shuffled_lifts = []
    for i in range(N_SHUFFLES):
        values = client_labels.to_numpy().copy()
        rng.shuffle(values)
        permuted = pd.Series(values, index=client_labels.index)
        swapped = df.assign(**{schema.TARGET: df[schema.UID].map(permuted).to_numpy()})
        scored = score_rings(
            membership, graph, swapped, rng=rng, attribute_columns=link_columns, n_permutations=1
        )
        value, _ = lift(scored)
        shuffled_lifts.append(value)
        print(f"  shuffle {i + 1}: {value:.3f}x")

    shuffled = np.asarray(shuffled_lifts, dtype=float)
    detector = {
        "observed_lift": observed_lift,
        "shuffled_mean": float(shuffled.mean()),
        "shuffled_sd": float(shuffled.std(ddof=1)),
        "collapses": bool(abs(shuffled.mean() - 1.0) < 0.35),
    }
    print(
        f"  shuffled mean {shuffled.mean():.3f}x (sd {shuffled.std(ddof=1):.3f}) -- "
        f"{'collapses to chance ✓' if detector['collapses'] else 'DOES NOT COLLAPSE'}"
    )

    results: dict[str, object] = {"detector": detector}

    # --- 2. the model harness ------------------------------------------------
    if not args.skip_model:
        print("\n-- harness: M1 trained on globally shuffled labels --")
        base = load_base()
        rng2 = rng_for("shuffle_model", cfg.seed)
        labels = base[schema.TARGET].to_numpy().copy()
        rng2.shuffle(labels)
        base[schema.TARGET] = labels

        features = tabular_feature_columns(base)
        frames = split_frames(base, features)
        runs = train_seed_sweep(
            frames,
            features=features,
            categorical=categorical_columns(base, features),
            params=cfg.model.params,
            num_boost_round=cfg.model.num_boost_round,
            early_stopping_rounds=cfg.model.early_stopping_rounds,
            seeds=[7, 8],
        )
        _, y_test = frames[Split.TEST]
        scores = [
            evaluate(y_test.to_numpy(), test_scores)["tpr_at_fpr_1pct"]
            for _, _, test_scores, _ in runs
        ]
        mean = float(np.mean(scores))
        results["harness"] = {
            "tpr_at_fpr_1pct": scores,
            "mean": mean,
            "at_chance": bool(abs(mean - 0.01) < 0.01),
        }
        print(f"  TPR@1%FPR on shuffled labels: {[f'{s:.4f}' for s in scores]}")
        print(
            f"  mean {mean:.4f} against a chance value of 0.0100 -- "
            f"{'at chance ✓' if results['harness']['at_chance'] else 'ABOVE CHANCE, investigate'}"
        )

    out = paths.report_path("shuffle_sanity.json")
    paths.ensure_parent(out)
    out.write_text(json.dumps(results, indent=2) + "\n")
    print(f"\nwrote {out}")
    record_run(cfg, script="97_shuffle_sanity", metrics={"detector_lift": observed_lift})


if __name__ == "__main__":
    main()
