#!/usr/bin/env python
"""Risk-propagation features: earlier transactions' stage-1 risk, shared across entities.

Stage 1 is a plain tabular model scored out-of-time in rolling windows (see
fds/risk_propagation.py). It exists only to generate these features; M1 is
untouched. Ends with a VALIDATION-only check against the control, so the
decision to keep the family never involves the test split.
"""

from __future__ import annotations

import time

import numpy as np

from fds import paths, schema
from fds.artifacts import input_ref, read_parquet, write_parquet
from fds.cli import base_parser, record_run, resolve
from fds.config import load_config
from fds.evaluation import evaluate
from fds.features import categorical_columns, split_frames, tabular_feature_columns
from fds.ingest import load_base
from fds.label_features import SECONDS_PER_DAY, label_feature_columns, CONTROL_PREFIX
from fds.models import train_seed_sweep
from fds.risk_propagation import PREFIX, propagate, rolling_scores
from fds.splits import Split

SCHEMA_VERSION = 1
STAGE1 = {
    "objective": "binary", "learning_rate": 0.1, "num_leaves": 64, "min_data_in_leaf": 100,
    "feature_fraction": 0.5, "bagging_fraction": 0.8, "bagging_freq": 1, "lambda_l2": 1.0,
    "max_bin": 255, "verbose": -1, "seed": 7,
}


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--delay", type=int, default=30, help="label maturity assumed by stage 1")
    parser.add_argument("--window", type=int, default=14)
    parser.add_argument("--rounds", type=int, default=150)
    parser.add_argument("--ctrl-config", default=str(paths.CONFIGS_DIR / "tuned" / "ctrl_d30.toml"))
    args = parser.parse_args()
    cfg = resolve(args)
    recipe = cfg.uid.recipe_name

    base = load_base()
    features = tabular_feature_columns(base)
    categorical = categorical_columns(base, features)
    schema.assert_no_denied_features(features)
    t = base[schema.TIME_RAW].to_numpy("int64")
    y = base[schema.TARGET].to_numpy()

    started = time.perf_counter()
    print(f"stage 1: rolling out-of-time scores ({len(features)} features, {args.window}-day windows, labels matured >= {args.delay}d)", flush=True)
    score = rolling_scores(
        base[features], t, y, categorical=categorical, params=STAGE1,
        delay_s=args.delay * SECONDS_PER_DAY, window_s=args.window * SECONDS_PER_DAY,
        first_start_s=30 * SECONDS_PER_DAY, rounds=args.rounds,
    )
    print(f"stage 1 done in {(time.perf_counter() - started) / 60:.1f} min", flush=True)
    scored = ~np.isnan(score)
    test = (base[schema.DAY] >= 151).to_numpy() & scored
    print(f"stage-1 AUC on scored test rows: {evaluate(y[test], score[test])['roc_auc']:.4f}  (scored {scored.mean():.1%} of rows)")

    uid_map = read_parquet(paths.uid_map_path(recipe))
    keyed = base.merge(uid_map, on=schema.KEY, validate="one_to_one")
    table = propagate(keyed, score)
    out = paths.DATA_ROOT / "riskfeat" / f"recipe={recipe}" / "riskfeat.parquet"
    write_parquet(table, out, schema_version=SCHEMA_VERSION,
                  params={"delay": args.delay, "window": args.window, "rounds": args.rounds},
                  inputs=[input_ref(paths.BASE_TRANSACTIONS)])
    print(f"wrote {out}  ({table.shape[1] - 1} features)", flush=True)

    # Validation-only check: does the family add anything on top of the control?
    df = base.merge(read_parquet(paths.labelfeat_path(recipe)), on=schema.KEY, validate="one_to_one")
    df = df.merge(table, on=schema.KEY, validate="one_to_one")
    ctrl = features + label_feature_columns(df, args.delay, CONTROL_PREFIX)
    rq = [c for c in df.columns if c.startswith(PREFIX)]
    params = load_config(args.ctrl_config).model.params
    y_val = split_frames(df, [schema.TARGET])[Split.VAL][1].to_numpy()
    print("\nvalidation check (3 seeds, control's tuned parameters):")
    results = {}
    for name, cols in (("ctrl", ctrl), ("ctrl+rq", ctrl + rq)):
        runs = train_seed_sweep(split_frames(df, cols), features=cols, categorical=categorical_columns(df, cols),
                                params=params, num_boost_round=cfg.model.num_boost_round,
                                early_stopping_rounds=cfg.model.early_stopping_rounds, seeds=[11, 22, 33])
        m = [evaluate(y_val, r[1]) for r in runs]
        results[name] = (np.mean([x["tpr_at_fpr_1pct"] for x in m]), np.mean([x["tpr_at_fpr_0.1pct"] for x in m]), np.mean([x["pr_auc"] for x in m]))
        print(f"  {name:<8} val TPR@1% {results[name][0]:.4f}   TPR@0.1% {results[name][1]:.4f}   PR-AUC {results[name][2]:.4f}", flush=True)
    print(f"  gain from rq on validation: TPR@1% {results['ctrl+rq'][0] - results['ctrl'][0]:+.4f}  TPR@0.1% {results['ctrl+rq'][1] - results['ctrl'][1]:+.4f}")
    record_run(cfg, script="85_risk_propagation")


if __name__ == "__main__":
    main()
