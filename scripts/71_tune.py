#!/usr/bin/env python
"""Tune a model's hyperparameters and write the winners to configs/tuned/.

Parameterised by model name so M1 and M2 receive identical treatment (D-16).
Tuning does not re-run on every pipeline execution: the winning parameters are
written to a committed file, which is what makes "genuinely well-tuned" an
auditable claim rather than an assertion.

Optimises validation TPR@1%FPR -- the same quantity the result is reported on.
Test is never touched.
"""

from __future__ import annotations

import json
import time

from fds import paths
from fds.cli import base_parser, record_run, resolve
from fds.features import categorical_columns, split_frames, tabular_feature_columns
from fds.ingest import load_base
from fds.tuning import TUNING_FPR, load_search_space, tune, winning_params


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--name", default="m1")
    parser.add_argument("--trials", type=int, default=40)
    parser.add_argument("--timeout", type=int, default=2700, help="seconds; Optuna stops after")
    parser.add_argument("--search", default=str(paths.CONFIGS_DIR / "search" / "lgbm.toml"))
    args = parser.parse_args()
    cfg = resolve(args)

    search = load_search_space(args.search)
    df = load_base()
    features = tabular_feature_columns(df)
    categorical = categorical_columns(df, features)
    frames = split_frames(df, features)
    print(
        f"tuning {args.name}: {len(features):,} features, "
        f"{args.trials} trials max, {args.timeout}s budget"
    )

    best_so_far = [0.0]

    def report(trial, value, best_iteration, seconds):
        marker = ""
        if value > best_so_far[0]:
            best_so_far[0] = value
            marker = "  <- best"
        print(
            f"  trial {trial.number:>3}  TPR@1%FPR {value:.4f}  "
            f"iters {best_iteration:>4}  {seconds:>5.1f}s{marker}",
            flush=True,
        )

    started = time.perf_counter()
    study = tune(
        frames,
        categorical=categorical,
        search=search,
        name=args.name,
        master_seed=cfg.seed,
        n_trials=args.trials,
        timeout=args.timeout,
        num_boost_round=cfg.model.num_boost_round,
        early_stopping_rounds=cfg.model.early_stopping_rounds,
        on_trial=report,
    )
    elapsed = time.perf_counter() - started

    completed = [t for t in study.trials if t.value is not None]
    print(f"\ncompleted {len(completed)} trials in {elapsed / 60:.1f} min")
    print(f"best validation TPR@{TUNING_FPR:.0%}FPR: {study.best_value:.4f}")
    print(f"best iteration: {study.best_trial.user_attrs.get('best_iteration')}")
    print("\n-- winning parameters --")
    for key, value in sorted(study.best_params.items()):
        print(f"  {key:<22} {value}")

    ranked = sorted(completed, key=lambda t: t.value, reverse=True)[:5]
    print("\n-- top 5 trials --")
    for trial in ranked:
        print(f"  trial {trial.number:>3}  TPR@1%FPR {trial.value:.4f}")

    params = winning_params(study, search)
    out_toml = paths.CONFIGS_DIR / "tuned" / f"{args.name}.toml"
    paths.ensure_parent(out_toml)
    lines = [
        f"# Tuned by scripts/71_tune.py on {time.strftime('%Y-%m-%d')}.",
        f"# {len(completed)} trials, objective = validation TPR@{TUNING_FPR:.0%}FPR = {study.best_value:.4f}.",
        f"# Search space: {args.search}. Do not hand-edit; re-run the tuner.",
        "",
        "[model]",
        f"num_boost_round = {cfg.model.num_boost_round}",
        f"early_stopping_rounds = {cfg.model.early_stopping_rounds}",
        "",
        "[model.params]",
    ]
    for key, value in sorted(params.items()):
        rendered = f'"{value}"' if isinstance(value, str) else value
        lines.append(f"{key} = {rendered}")
    out_toml.write_text("\n".join(lines) + "\n")
    print(f"\nwrote {out_toml}")

    out_json = paths.report_path(f"{args.name}_tuning.json")
    paths.ensure_parent(out_json)
    out_json.write_text(
        json.dumps(
            {
                "name": args.name,
                "n_trials": len(completed),
                "elapsed_minutes": round(elapsed / 60, 2),
                "objective": f"val_tpr_at_fpr_{TUNING_FPR}",
                "best_value": study.best_value,
                "best_params": study.best_params,
                "best_iteration": study.best_trial.user_attrs.get("best_iteration"),
                "all_trials": [
                    {"number": t.number, "value": t.value, "params": t.params} for t in completed
                ],
            },
            indent=2,
        )
        + "\n"
    )
    print(f"wrote {out_json}")
    record_run(cfg, script=f"71_tune_{args.name}", metrics={"best_value": study.best_value})


if __name__ == "__main__":
    main()
