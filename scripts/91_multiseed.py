#!/usr/bin/env python
"""M1 vs M2 across several seeds -- the comparison that is actually defensible.

D-42 measured a seed-only spread of 0.033 in test TPR@1%FPR, which is larger
than any M1/M2 gap seen so far. A single training run is therefore not a
measurement on this problem, and the headline claim cannot rest on one.

Design: both feature sets are trained at each seed, sharing that seed's training
randomness, so the per-seed difference isolates the feature set. The reported
quantity is the distribution of paired differences, not two point estimates.

Reported on three strata, because structural features are non-trivial on roughly
1% of transactions and a real effect would be diluted away on the full set while
a subpopulation-only report would overstate its reach.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from fds import paths, schema
from fds.artifacts import read_parquet
from fds.cli import base_parser, record_run, resolve
from fds.evaluation import evaluate
from fds.features import (
    categorical_columns,
    join_structural,
    split_frames,
    structural_feature_columns,
    tabular_feature_columns,
)
from fds.ingest import load_base
from fds.models import train_seed_sweep
from fds.splits import Split

SEEDS = [11, 22, 33, 44, 55]


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--recipe", default=None)
    parser.add_argument("--seeds", type=int, nargs="*", default=SEEDS)
    args = parser.parse_args()
    cfg = resolve(args)
    recipe = args.recipe or cfg.uid.recipe_name

    attach_path = paths.attach_path(
        recipe, cfg.graph.hub_min_degree, cfg.graph.hub_max_degree, cfg.snapshots.cadence_days
    )
    attach = read_parquet(attach_path)
    df = join_structural(load_base(), attach)
    print(f"structural features from {attach_path}")

    structural = structural_feature_columns(df)
    m2_features = tabular_feature_columns(df)
    m1_features = [c for c in m2_features if c not in structural]
    schema.assert_no_denied_features(m2_features)
    print(f"M1: {len(m1_features):,} features   M2: {len(m2_features):,} (+{len(structural)})")
    print(f"seeds: {args.seeds}")

    # Strata membership, fixed once so both models are judged on identical rows.
    frames_m1 = split_frames(df, m1_features)
    frames_m2 = split_frames(df, m2_features)
    y_test = frames_m1[Split.TEST][1].to_numpy()
    test_index = frames_m1[Split.TEST][0].index
    structure_flag = df.loc[test_index, "has_structure"].to_numpy()
    linked_flag = df.loc[test_index, "st_degree"].fillna(0).to_numpy() > 0

    strata = {
        "full_test": np.ones_like(y_test, dtype=bool),
        "has_snapshot": structure_flag,
        "linked_clients": linked_flag,
    }
    for name, mask in strata.items():
        print(f"  {name:<16} {int(mask.sum()):>7,} rows  {int(y_test[mask].sum()):>5,} fraud")

    common = {
        "params": cfg.model.params,
        "num_boost_round": cfg.model.num_boost_round,
        "early_stopping_rounds": cfg.model.early_stopping_rounds,
        "seeds": args.seeds,
    }
    print("\ntraining M1 across seeds")
    m1_runs = train_seed_sweep(
        frames_m1, features=m1_features, categorical=categorical_columns(df, m1_features), **common
    )
    print("training M2 across seeds")
    m2_runs = train_seed_sweep(
        frames_m2, features=m2_features, categorical=categorical_columns(df, m2_features), **common
    )

    rows = []
    for (seed, _, m1_test, m1_iter), (_, _, m2_test, m2_iter) in zip(m1_runs, m2_runs, strict=True):
        for name, mask in strata.items():
            if y_test[mask].sum() < 10:
                continue
            a = evaluate(y_test[mask], m1_test[mask])
            b = evaluate(y_test[mask], m2_test[mask])
            rows.append(
                {
                    "seed": seed,
                    "stratum": name,
                    "m1_tpr": a["tpr_at_fpr_1pct"],
                    "m2_tpr": b["tpr_at_fpr_1pct"],
                    "diff": b["tpr_at_fpr_1pct"] - a["tpr_at_fpr_1pct"],
                    "m1_pr_auc": a["pr_auc"],
                    "m2_pr_auc": b["pr_auc"],
                    "m1_iter": m1_iter,
                    "m2_iter": m2_iter,
                }
            )
    frame = pd.DataFrame(rows)

    print(
        f"\n{'stratum':<16}{'M1 mean':>10}{'M1 sd':>8}{'M2 mean':>10}{'M2 sd':>8}"
        f"{'mean diff':>11}{'sd diff':>9}{'wins':>6}"
    )
    print("-" * 78)
    summary = {}
    for name in strata:
        block = frame[frame["stratum"] == name]
        if block.empty:
            continue
        diffs = block["diff"].to_numpy()
        wins = int((diffs > 0).sum())
        summary[name] = {
            "m1_mean": float(block["m1_tpr"].mean()),
            "m1_sd": float(block["m1_tpr"].std(ddof=1)),
            "m2_mean": float(block["m2_tpr"].mean()),
            "m2_sd": float(block["m2_tpr"].std(ddof=1)),
            "mean_diff": float(diffs.mean()),
            "sd_diff": float(diffs.std(ddof=1)),
            "wins": wins,
            "n_seeds": len(diffs),
            "per_seed_diffs": [float(d) for d in diffs],
        }
        s = summary[name]
        print(
            f"{name:<16}{s['m1_mean']:>10.4f}{s['m1_sd']:>8.4f}{s['m2_mean']:>10.4f}"
            f"{s['m2_sd']:>8.4f}{s['mean_diff']:>+11.4f}{s['sd_diff']:>9.4f}"
            f"{wins:>4}/{len(diffs)}"
        )

    print("\n-- verdict (paired on training seed) --")
    for name, s in summary.items():
        se = s["sd_diff"] / np.sqrt(s["n_seeds"]) if s["n_seeds"] > 1 else float("nan")
        ratio = s["mean_diff"] / se if se and se > 0 else float("nan")
        call = "real" if abs(ratio) > 2.5 else "within noise"
        print(f"  {name:<16} {s['mean_diff']:+.4f} +/- {se:.4f} (se)  t~{ratio:+.1f}  {call}")

    out = paths.report_path("multiseed_m1_vs_m2.json")
    paths.ensure_parent(out)
    out.write_text(
        json.dumps(
            {"seeds": args.seeds, "summary": summary, "runs": frame.to_dict("records")}, indent=2
        )
        + "\n"
    )
    print(f"\nwrote {out}")
    record_run(cfg, script="91_multiseed", metrics={k: v["mean_diff"] for k, v in summary.items()})


if __name__ == "__main__":
    main()
