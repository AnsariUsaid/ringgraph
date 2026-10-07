#!/usr/bin/env python
"""Tune the control and graph models exactly as M1 was tuned (D-16 parity).

Same search space, same objective (validation TPR@1%FPR), same early stopping.
Test is never touched. The delay used for tuning is fixed up front and the
winning parameters are reused for the other delays.

  --family ctrl   M1 + tabular-key delayed history
  --family graph  M1 + everything relational (the headline model)
"""

from __future__ import annotations

import json
import time

from fds import paths, schema
from fds.artifacts import read_parquet
from fds.cli import base_parser, record_run, resolve
from fds.features import categorical_columns, split_frames, tabular_feature_columns
from fds.ingest import load_base
from fds.label_features import AGG_PREFIX, CONTROL_PREFIX, GRAPH_PREFIX, label_feature_columns
from fds.relational_features import LABEL_PREFIX, PROP_PREFIX, STRUCT_PREFIX
from fds.tuning import TUNING_FPR, load_search_space, tune, winning_params


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--family", choices=["ctrl", "graph"], required=True)
    parser.add_argument("--delay", type=int, default=30)
    parser.add_argument("--trials", type=int, default=40)
    parser.add_argument("--timeout", type=int, default=2700)
    parser.add_argument("--search", default=str(paths.CONFIGS_DIR / "search" / "lgbm.toml"))
    args = parser.parse_args()
    cfg = resolve(args)
    recipe, d = cfg.uid.recipe_name, args.delay

    base = load_base()
    m1 = tabular_feature_columns(base)
    df = base.merge(read_parquet(paths.labelfeat_path(recipe)), on=schema.KEY, how="left", validate="one_to_one")
    df = df.merge(read_parquet(paths.relfeat_path(recipe)), on=schema.KEY, how="left", validate="one_to_one")
    ctrl = label_feature_columns(df, d, CONTROL_PREFIX)
    if args.family == "ctrl":
        features = m1 + ctrl
    else:
        v1 = label_feature_columns(df, d, AGG_PREFIX) + label_feature_columns(df, d, GRAPH_PREFIX)
        rel = [c for c in df.columns if c.startswith((f"{LABEL_PREFIX}{d}_", f"{PROP_PREFIX}{d}_", STRUCT_PREFIX))]
        features = m1 + ctrl + v1 + rel
    schema.assert_no_denied_features(features)
    name = f"{args.family}_d{d}"
    print(f"tuning {name}: {len(features):,} features, {args.trials} trials max, {args.timeout}s", flush=True)

    best = [0.0]

    def report(trial, value, best_iteration, seconds):
        mark = "  <- best" if value > best[0] else ""
        best[0] = max(best[0], value)
        print(f"  trial {trial.number:>3}  TPR@1%FPR {value:.4f}  iters {best_iteration:>4}  {seconds:>5.1f}s{mark}", flush=True)

    search = load_search_space(args.search)
    started = time.perf_counter()
    study = tune(
        split_frames(df, features),
        categorical=categorical_columns(df, features),
        search=search,
        name=name,
        master_seed=cfg.seed,
        n_trials=args.trials,
        timeout=args.timeout,
        num_boost_round=cfg.model.num_boost_round,
        early_stopping_rounds=cfg.model.early_stopping_rounds,
        on_trial=report,
    )
    done = [t for t in study.trials if t.value is not None]
    print(f"\n{len(done)} trials in {(time.perf_counter() - started) / 60:.1f} min; best validation TPR@{TUNING_FPR:.0%}FPR {study.best_value:.4f}")

    params = winning_params(study, search)
    out = paths.CONFIGS_DIR / "tuned" / f"{name}.toml"
    lines = [
        f"# Tuned by scripts/94_tune_graph.py on {time.strftime('%Y-%m-%d')}: family={args.family}, delay={d}d.",
        f"# {len(done)} trials, objective = validation TPR@{TUNING_FPR:.0%}FPR = {study.best_value:.4f}.",
        "",
        "[model]",
        f"num_boost_round = {cfg.model.num_boost_round}",
        f"early_stopping_rounds = {cfg.model.early_stopping_rounds}",
        "",
        "[model.params]",
    ]
    for key, value in sorted(params.items()):
        lines.append(f'{key} = "{value}"' if isinstance(value, str) else f"{key} = {value}")
    out.write_text("\n".join(lines) + "\n")
    print(f"wrote {out}")
    paths.report_path(f"{name}_tuning.json").write_text(
        json.dumps({"best_value": study.best_value, "best_params": study.best_params,
                    "trials": [{"n": t.number, "value": t.value, "params": t.params} for t in done]}, indent=2) + "\n"
    )
    record_run(cfg, script=f"94_tune_{name}", metrics={"best_value": study.best_value})


if __name__ == "__main__":
    main()
