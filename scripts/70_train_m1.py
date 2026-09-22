#!/usr/bin/env python
"""M1: the tabular baseline the graph has to beat.

Strictly temporal: fit on days 0-119, early-stop on 120-150, evaluate on
151-181. No shuffling anywhere.

The feature set deliberately includes the identity block (DeviceInfo, id_*).
A baseline that lacked them would make the later M2-M1 gap partly a
categorical-encoding effect rather than a structural one, and "structure is
additive" would be overstated.
"""

from __future__ import annotations

import json

import pandas as pd

from fds import paths
from fds.artifacts import input_ref, write_parquet
from fds.cli import base_parser, record_run, resolve
from fds.evaluation import evaluate
from fds.features import (
    categorical_columns,
    prediction_frame,
    split_frames,
    tabular_feature_columns,
)
from fds.ingest import load_base
from fds.models import feature_importance, train_lightgbm
from fds.splits import Split

PREDICTIONS_SCHEMA_VERSION = 1


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--name", default="m1")
    args = parser.parse_args()
    cfg = resolve(args)

    df = load_base()
    features = tabular_feature_columns(df)
    categorical = categorical_columns(df, features)
    print(f"features: {len(features):,} ({len(categorical)} categorical)")

    frames = split_frames(df, features)
    for split, (X, y) in frames.items():
        print(f"  {split!s:<6} {len(X):>8,} rows  {int(y.sum()):>6,} fraud  {y.mean():.4f}")

    model = train_lightgbm(
        frames,
        features=features,
        categorical=categorical,
        params=cfg.model.params,
        num_boost_round=cfg.model.num_boost_round,
        early_stopping_rounds=cfg.model.early_stopping_rounds,
        master_seed=cfg.seed,
        name=args.name,
    )
    print(f"\nbest iteration: {model.best_iteration}")

    scores = {split: pd.Series(model.predict(X)) for split, (X, _) in frames.items()}
    metrics = {}
    print(f"\n{'split':<8}{'PR-AUC':>9}{'ROC-AUC':>9}{'TPR@1%':>9}{'TPR@0.1%':>10}")
    print("-" * 45)
    for split in (Split.VAL, Split.TEST):
        X, y = frames[split]
        m = evaluate(y.to_numpy(), scores[split].to_numpy())
        metrics[str(split)] = m
        print(
            f"{split!s:<8}{m['pr_auc']:>9.4f}{m['roc_auc']:>9.4f}"
            f"{m['tpr_at_fpr_1pct']:>9.4f}{m['tpr_at_fpr_0.1pct']:>10.4f}"
        )

    predictions = prediction_frame(df, scores)
    run_key = cfg.run_key()
    write_parquet(
        predictions,
        paths.preds_path(args.name, run_key),
        schema_version=PREDICTIONS_SCHEMA_VERSION,
        params={"model": args.name, "features": features, "best_iteration": model.best_iteration},
        inputs=[input_ref(paths.BASE_TRANSACTIONS)],
        extra={"metrics": metrics, "lgbm_params": model.params},
    )
    print(f"\nwrote predictions to {paths.preds_path(args.name, run_key)}")

    importance = feature_importance(model)
    print("\n-- top features by gain --")
    for _, row in importance.head(12).iterrows():
        print(f"  {row['feature']:<20} {row['share']:.4f}")

    out = paths.report_path(f"{args.name}_metrics.json")
    paths.ensure_parent(out)
    out.write_text(
        json.dumps(
            {
                "run_key": run_key,
                "n_features": len(features),
                "best_iteration": model.best_iteration,
                "metrics": metrics,
                "top_features": importance.to_dict("records"),
            },
            indent=2,
        )
        + "\n"
    )
    print(f"wrote {out}")
    record_run(cfg, script=f"70_train_{args.name}", metrics=metrics.get("test", {}))


if __name__ == "__main__":
    main()
