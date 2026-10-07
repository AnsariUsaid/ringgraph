#!/usr/bin/env python
"""Causal client behaviour profile (see fds/client_profile.py) plus a VALIDATION-only check.

The check trains the control with and without the family on the validation split's
terms (3 seeds, the control's tuned parameters); test is never touched.
"""

from __future__ import annotations

import numpy as np

from fds import paths, schema
from fds.artifacts import input_ref, read_parquet, write_parquet
from fds.cli import base_parser, record_run, resolve
from fds.client_profile import PREFIX, base_columns, build_profile
from fds.config import load_config
from fds.evaluation import evaluate
from fds.features import categorical_columns, split_frames, tabular_feature_columns
from fds.ingest import load_base
from fds.label_features import CONTROL_PREFIX, label_feature_columns
from fds.models import train_seed_sweep
from fds.splits import Split

SCHEMA_VERSION = 1


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--ctrl-config", default=str(paths.CONFIGS_DIR / "tuned" / "ctrl_d30.toml"))
    args = parser.parse_args()
    cfg = resolve(args)
    recipe = cfg.uid.recipe_name

    keyed = load_base(columns=base_columns()).merge(read_parquet(paths.uid_map_path(recipe)), on=schema.KEY, validate="one_to_one")
    table = build_profile(keyed)
    out = paths.DATA_ROOT / "profile" / f"recipe={recipe}" / "profile.parquet"
    write_parquet(table, out, schema_version=SCHEMA_VERSION, inputs=[input_ref(paths.BASE_TRANSACTIONS)])
    print(f"wrote {out}  ({table.shape[1] - 1} features)", flush=True)

    base = load_base()
    m1 = tabular_feature_columns(base)
    df = base.merge(read_parquet(paths.labelfeat_path(recipe)), on=schema.KEY, validate="one_to_one").merge(table, on=schema.KEY, validate="one_to_one")
    ctrl = m1 + label_feature_columns(df, 30, CONTROL_PREFIX)
    cp = [c for c in df.columns if c.startswith(PREFIX)]
    params = load_config(args.ctrl_config).model.params
    y_val = split_frames(df, [schema.TARGET])[Split.VAL][1].to_numpy()
    print("\nvalidation check (3 seeds, control's tuned parameters):", flush=True)
    res = {}
    for name, cols in (("ctrl", ctrl), ("ctrl+cp", ctrl + cp)):
        runs = train_seed_sweep(split_frames(df, cols), features=cols, categorical=categorical_columns(df, cols), params=params,
                                num_boost_round=cfg.model.num_boost_round, early_stopping_rounds=cfg.model.early_stopping_rounds, seeds=[11, 22, 33])
        m = [evaluate(y_val, r[1]) for r in runs]
        res[name] = tuple(np.mean([x[k] for x in m]) for k in ("tpr_at_fpr_1pct", "tpr_at_fpr_0.1pct", "pr_auc"))
        print(f"  {name:<8} val TPR@1% {res[name][0]:.4f}   TPR@0.1% {res[name][1]:.4f}   PR-AUC {res[name][2]:.4f}", flush=True)
    print(f"  gain from cp on validation: TPR@1% {res['ctrl+cp'][0] - res['ctrl'][0]:+.4f}  TPR@0.1% {res['ctrl+cp'][1] - res['ctrl'][1]:+.4f}")
    record_run(cfg, script="86_client_profile")


if __name__ == "__main__":
    main()
