"""Hyperparameter search, shared by every model in the ladder.

plan.md requires M1 to be genuinely well-tuned, since the whole claim is "lift
over a strong baseline". The corollary it does not state (D-16) is that M2 must
be tuned with the *identical* search space, trial budget and early-stopping
protocol: tune M1 hard and M2 casually and the lift is understated; do the
reverse and the lift is a tuning artefact rather than a structural one.

That parity is enforced structurally — this module takes the model name as a
parameter, so an asymmetric budget requires a deliberate act rather than an
oversight.

Tuning optimises **validation TPR at 1% FPR**, the same quantity the result is
reported on. Optimising a proxy like ROC-AUC and reporting TPR@FPR would mean
the model was selected for something other than what it is judged on. Test is
never touched.
"""

from __future__ import annotations

import time
import tomllib
from pathlib import Path
from typing import Any

import lightgbm as lgb
import optuna

from fds.evaluation import tpr_at_fpr
from fds.rng import seed_for
from fds.splits import Split

optuna.logging.set_verbosity(optuna.logging.WARNING)

TUNING_FPR = 0.01


def load_search_space(path: Path | str) -> dict[str, Any]:
    with Path(path).open("rb") as fh:
        return tomllib.load(fh)


def _suggest(trial: optuna.Trial, name: str, spec: dict[str, Any]) -> Any:
    kind = spec["type"]
    if kind == "int":
        return trial.suggest_int(name, spec["low"], spec["high"], log=spec.get("log", False))
    if kind == "float":
        return trial.suggest_float(name, spec["low"], spec["high"], log=spec.get("log", False))
    if kind == "categorical":
        return trial.suggest_categorical(name, spec["choices"])
    raise ValueError(f"unsupported search-space type {kind!r} for {name!r}")


def tune(
    frames: dict[Split, tuple[Any, Any]],
    *,
    categorical: list[str],
    search: dict[str, Any],
    name: str,
    master_seed: int,
    n_trials: int = 40,
    timeout: int | None = None,
    num_boost_round: int = 700,
    early_stopping_rounds: int = 50,
    on_trial: Any = None,
) -> optuna.Study:
    """Search, returning the completed study.

    The binned LightGBM ``Dataset`` is constructed once and reused across trials.
    Rebuilding it per trial would dominate the runtime and, on an 8GB machine,
    churn roughly a gigabyte of memory forty times over.
    """
    X_train, y_train = frames[Split.TRAIN]
    X_val, y_val = frames[Split.VAL]
    fixed = dict(search.get("fixed", {}))
    space = search["space"]

    negative, positive = int((y_train == 0).sum()), int((y_train == 1).sum())
    scale_pos_weight = negative / max(positive, 1)

    train_set = lgb.Dataset(
        X_train, label=y_train, categorical_feature=categorical, free_raw_data=False
    )
    val_set = lgb.Dataset(
        X_val,
        label=y_val,
        categorical_feature=categorical,
        reference=train_set,
        free_raw_data=False,
    )
    train_set.construct()
    val_set.construct()

    y_val_array = y_val.to_numpy()

    def objective(trial: optuna.Trial) -> float:
        trial_start = time.perf_counter()
        params = dict(fixed)
        params.update({key: _suggest(trial, key, spec) for key, spec in space.items()})
        params["scale_pos_weight"] = scale_pos_weight
        params["seed"] = seed_for(f"tune_{name}_{trial.number}", master_seed)
        params["verbose"] = -1

        booster = lgb.train(
            params,
            train_set,
            num_boost_round=num_boost_round,
            valid_sets=[val_set],
            callbacks=[lgb.early_stopping(early_stopping_rounds, verbose=False)],
        )
        scores = booster.predict(X_val, num_iteration=booster.best_iteration)
        trial.set_user_attr("best_iteration", booster.best_iteration)
        value = tpr_at_fpr(y_val_array, scores, TUNING_FPR)["tpr"]
        if on_trial is not None:
            on_trial(trial, value, booster.best_iteration, time.perf_counter() - trial_start)
        return value

    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=seed_for(f"sampler_{name}", master_seed)),
        study_name=f"{name}_lgbm",
    )
    study.optimize(objective, n_trials=n_trials, timeout=timeout, show_progress_bar=False)
    return study


def winning_params(study: optuna.Study, search: dict[str, Any]) -> dict[str, Any]:
    params = dict(search.get("fixed", {}))
    params.update(study.best_params)
    return params
