#!/usr/bin/env python
"""M1 vs control vs M3 over delays and seeds -- the headline experiment.

  M1  : the existing tabular model, untouched (M1's tuned parameters).
  C1  : M1 + delayed-label features from tabular keys only (the control).
  M3a : control + compact cross-key graph aggregates (labels + label-free velocity).
  M3b : M3a + every per-key graph column. The headline M3 is whichever wins on validation.

All three share each seed's training randomness, so differences are paired. Every
delay is reported, not the best one. Nothing here is tuned on the test split.
Scores are averaged over seeds before the paired bootstrap, so the interval
reflects test-set sampling while the per-seed table shows training noise.
"""

from __future__ import annotations

import json

import numpy as np

from fds import paths, schema
from fds.artifacts import read_parquet
from fds.cli import base_parser, record_run, resolve
from fds.evaluation import evaluate, paired_bootstrap_difference
from fds.features import categorical_columns, split_frames, tabular_feature_columns
from fds.ingest import load_base
from fds.label_features import AGG_PREFIX, CONTROL_PREFIX, DELAYS, GRAPH_PREFIX, label_feature_columns
from fds.models import train_seed_sweep
from fds.splits import Split

SEEDS = [11, 22, 33, 44, 55]
FPRS = {"tpr_at_fpr_1pct": 0.01, "tpr_at_fpr_0.1pct": 0.001}


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, nargs="*", default=SEEDS)
    parser.add_argument("--delays", type=int, nargs="*", default=list(DELAYS))
    parser.add_argument("--out", default="label_sweep")
    args = parser.parse_args()
    cfg = resolve(args)

    base = load_base()
    m1_features = tabular_feature_columns(base)
    table = read_parquet(paths.labelfeat_path(cfg.uid.recipe_name))
    df = base.merge(table, on=schema.KEY, how="left", validate="one_to_one")
    del base
    schema.assert_no_denied_features(m1_features)
    print(f"M1: {len(m1_features):,} features   seeds: {args.seeds}   delays: {args.delays}", flush=True)

    test_idx = split_frames(df, [schema.KEY])[Split.TEST][0].index
    y = df.loc[test_idx, schema.TARGET].to_numpy()

    val_idx = split_frames(df, [schema.KEY])[Split.VAL][0].index
    y_val = df.loc[val_idx, schema.TARGET].to_numpy()

    def train(features: list[str], label: str) -> tuple[np.ndarray, np.ndarray]:
        print(f"\n== training {label} ({len(features):,} features)", flush=True)
        runs = train_seed_sweep(
            split_frames(df, features),
            features=features,
            categorical=categorical_columns(df, features),
            params=cfg.model.params,
            num_boost_round=cfg.model.num_boost_round,
            early_stopping_rounds=cfg.model.early_stopping_rounds,
            seeds=args.seeds,
        )
        for seed, v, s, it in runs:
            print(
                f"   seed {seed}: iter {it}  val TPR@1% {evaluate(y_val, v)['tpr_at_fpr_1pct']:.4f}"
                f"  test TPR@1% {evaluate(y, s)['tpr_at_fpr_1pct']:.4f}",
                flush=True,
            )
        return np.stack([r[1] for r in runs]), np.stack([r[2] for r in runs])

    val_scores: dict[tuple[int, str], np.ndarray] = {}
    m1v, m1 = train(m1_features, "M1")
    rng = np.random.default_rng(cfg.seed)
    report: dict = {"seeds": args.seeds, "delays": {}, "selected": {}}
    for d in args.delays:
        ctrl = m1_features + label_feature_columns(df, d, CONTROL_PREFIX)
        agg = label_feature_columns(df, d, AGG_PREFIX)
        per_key = label_feature_columns(df, d, GRAPH_PREFIX)
        # c1 = control; m3a = control + compact graph aggregates; m3b = + every per-key column.
        models = {"m1": (m1v, m1)}
        models["c1"] = train(ctrl, f"C1 control, delay {d}d")
        models["m3a"] = train(ctrl + agg, f"M3a compact graph, delay {d}d")
        models["m3b"] = train(ctrl + agg + per_key, f"M3b full graph, delay {d}d")

        # The headline M3 is chosen on VALIDATION (mean TPR@1% over seeds), never on test.
        val_tpr = {
            m: float(np.mean([evaluate(y_val, r)["tpr_at_fpr_1pct"] for r in v]))
            for m, (v, _) in models.items()
            if m.startswith("m3")
        }
        chosen = max(val_tpr, key=val_tpr.get)
        report["selected"][str(d)] = {"chosen_on_validation": chosen, "val_tpr_at_1pct": val_tpr}
        print(f"\n  delay {d}d: validation picks {chosen}  {val_tpr}", flush=True)

        exposed = df.loc[test_idx, f"{AGG_PREFIX}{d}_n_exposed_le50"].to_numpy() > 0
        strata = {"full_test": np.ones_like(y, dtype=bool), "rare_graph_exposure": exposed}
        entry: dict = {}
        for sname, mask in strata.items():
            block = {"n": int(mask.sum()), "n_fraud": int(y[mask].sum())}
            for mname, (_, s) in models.items():
                per_seed = [evaluate(y[mask], r[mask]) for r in s]
                for k in FPRS:
                    block[f"{mname}_{k}"] = [p[k] for p in per_seed]
            for k, fpr in FPRS.items():
                for a, b in (("m1", "c1"), ("m1", "m3a"), ("m1", "m3b"), ("c1", "m3a"), ("c1", "m3b")):
                    block[f"{b}_minus_{a}_{k}"] = paired_bootstrap_difference(
                        y[mask],
                        models[a][1].mean(0)[mask],
                        models[b][1].mean(0)[mask],
                        target_fpr=fpr,
                        rng=rng,
                        n_boot=500,
                    )
            entry[sname] = block
        report["delays"][str(d)] = entry

        print(f"\n---- delay {d}d  (test, mean over {len(args.seeds)} seeds) ----")
        for sname, block in entry.items():
            print(f" [{sname}] {block['n']:,} rows, {block['n_fraud']:,} fraud")
            for k in FPRS:
                means = "   ".join(f"{m.upper()} {np.mean(block[f'{m}_{k}']):.4f}" for m in models)
                print(f"   {k:<18} {means}")
                for a, b in (("m1", "c1"), ("m1", "m3a"), ("m1", "m3b"), ("c1", "m3a"), ("c1", "m3b")):
                    r = block[f"{b}_minus_{a}_{k}"]
                    print(
                        f"      {b.upper()}-{a.upper()}: {r['observed_difference']:+.4f}  95% CI "
                        f"[{r['ci_low']:+.4f}, {r['ci_high']:+.4f}]  excludes 0: {r['excludes_zero']}"
                    )

    out = paths.report_path(f"{args.out}.json")
    paths.ensure_parent(out)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"\nwrote {out}")
    record_run(cfg, script="92_label_sweep")


if __name__ == "__main__":
    main()
