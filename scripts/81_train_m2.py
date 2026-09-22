#!/usr/bin/env python
"""M2: the structure-augmented model. M1's features plus graph structure.

Identical to M1 in every other respect -- same split, same feature handling,
same round budget -- so any difference in score is attributable to the
structural columns rather than to protocol.

Structural features are NaN for transactions with no prior snapshot, never zero
(D-20). LightGBM handles missing natively, and zero would be a lie: it is a real
degree value, so filling it would teach the model that "no history yet" and
"isolated node" are the same thing.
"""

from __future__ import annotations

import json

import pandas as pd

from fds import paths, schema
from fds.artifacts import input_ref, read_parquet, write_parquet
from fds.cli import base_parser, record_run, resolve
from fds.evaluation import evaluate
from fds.features import (
    categorical_columns,
    join_structural,
    prediction_frame,
    split_frames,
    structural_feature_columns,
    tabular_feature_columns,
)
from fds.ingest import load_base
from fds.models import feature_importance, train_lightgbm
from fds.splits import Split

PREDICTIONS_SCHEMA_VERSION = 1


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--name", default="m2")
    parser.add_argument("--recipe", default=None)
    args = parser.parse_args()
    cfg = resolve(args)
    recipe = args.recipe or cfg.uid.recipe_name

    attach_path = paths.attach_path(
        recipe, cfg.graph.hub_min_degree, cfg.graph.hub_max_degree, cfg.snapshots.cadence_days
    )
    if not attach_path.exists():
        raise SystemExit(f"{attach_path} missing -- run scripts/80_snapshot_features.py first")
    print(f"structural features from {attach_path}")

    attach = read_parquet(attach_path)
    df = join_structural(load_base(), attach)

    features = tabular_feature_columns(df)
    structural = structural_feature_columns(df)
    categorical = categorical_columns(df, features)
    schema.assert_no_denied_features(features)
    print(f"features: {len(features):,} total, {len(structural)} structural")
    print(f"  rows with structure: {df['has_structure'].mean():.4f}")

    frames = split_frames(df, features)
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
        _, y = frames[split]
        m = evaluate(y.to_numpy(), scores[split].to_numpy())
        metrics[str(split)] = m
        print(
            f"{split!s:<8}{m['pr_auc']:>9.4f}{m['roc_auc']:>9.4f}"
            f"{m['tpr_at_fpr_1pct']:>9.4f}{m['tpr_at_fpr_0.1pct']:>10.4f}"
        )

    run_key = cfg.run_key()
    write_parquet(
        prediction_frame(df, scores),
        paths.preds_path(args.name, run_key),
        schema_version=PREDICTIONS_SCHEMA_VERSION,
        params={"model": args.name, "features": features, "structural": structural},
        inputs=[input_ref(paths.BASE_TRANSACTIONS), input_ref(attach_path)],
        extra={"metrics": metrics},
    )
    print(f"\nwrote predictions to {paths.preds_path(args.name, run_key)}")

    importance = feature_importance(model, top=40)
    structural_rank = importance[importance["feature"].isin(structural)]
    print("\n-- structural features in the top 40 by gain --")
    if structural_rank.empty:
        print("  none -- the model found no use for them")
    else:
        for _, row in structural_rank.iterrows():
            rank = importance.index[importance["feature"] == row["feature"]][0] + 1
            print(f"  #{rank:<3} {row['feature']:<24} {row['share']:.4f}")

    out = paths.report_path(f"{args.name}_metrics.json")
    paths.ensure_parent(out)
    out.write_text(
        json.dumps(
            {
                "run_key": run_key,
                "attach": str(attach_path),
                "n_features": len(features),
                "structural_features": structural,
                "has_structure_share": float(df["has_structure"].mean()),
                "metrics": metrics,
                "top_features": importance.head(20).to_dict("records"),
            },
            indent=2,
        )
        + "\n"
    )
    print(f"wrote {out}")
    record_run(cfg, script=f"81_train_{args.name}", metrics=metrics.get("test", {}))


if __name__ == "__main__":
    main()
