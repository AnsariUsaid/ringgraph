"""LightGBM training under the temporal split.

The baseline has to be genuinely well-tuned: plan.md's entire claim is "lift over
a strong baseline", so a lazy M1 invalidates the result more thoroughly than a
weak graph model would. The corollary, which plan.md does not state but which is
load-bearing (D-16), is **tuning parity** — M2 must be tuned with the identical
search space, trial budget and early-stopping protocol. One function takes the
model name as a parameter so asymmetry requires a deliberate act.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd

from fds.rng import seed_for
from fds.splits import Split


@dataclass
class TrainedModel:
    booster: lgb.Booster
    features: list[str]
    categorical: list[str]
    best_iteration: int
    params: dict[str, Any]

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self.booster.predict(X[self.features], num_iteration=self.best_iteration)


def train_lightgbm(
    frames: dict[Split, tuple[pd.DataFrame, pd.Series]],
    *,
    features: list[str],
    categorical: list[str],
    params: dict[str, Any],
    num_boost_round: int,
    early_stopping_rounds: int,
    master_seed: int,
    name: str,
) -> TrainedModel:
    """Fit on train, early-stop on validation. Test is never touched here.

    Class imbalance is handled with ``scale_pos_weight`` rather than by
    resampling: plan.md forbids oversampling across the temporal boundary, and
    reweighting avoids inventing rows altogether.
    """
    X_train, y_train = frames[Split.TRAIN]
    X_val, y_val = frames[Split.VAL]

    resolved = dict(params)
    resolved.setdefault("objective", "binary")
    resolved["seed"] = seed_for(f"lgbm_{name}", master_seed)
    resolved["verbose"] = -1
    negative, positive = int((y_train == 0).sum()), int((y_train == 1).sum())
    resolved.setdefault("scale_pos_weight", negative / max(positive, 1))

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

    booster = lgb.train(
        resolved,
        train_set,
        num_boost_round=num_boost_round,
        valid_sets=[val_set],
        valid_names=["val"],
        callbacks=[
            lgb.early_stopping(early_stopping_rounds, verbose=False),
            lgb.log_evaluation(period=100),
        ],
    )
    return TrainedModel(
        booster=booster,
        features=features,
        categorical=categorical,
        best_iteration=booster.best_iteration,
        params=resolved,
    )


def feature_importance(model: TrainedModel, top: int = 25) -> pd.DataFrame:
    gains = model.booster.feature_importance(importance_type="gain")
    frame = pd.DataFrame({"feature": model.booster.feature_name(), "gain": gains})
    frame["share"] = frame["gain"] / frame["gain"].sum()
    return frame.sort_values("gain", ascending=False, ignore_index=True).head(top)


def train_seed_sweep(
    frames: dict[Split, tuple[pd.DataFrame, pd.Series]],
    *,
    features: list[str],
    categorical: list[str],
    params: dict[str, Any],
    num_boost_round: int,
    early_stopping_rounds: int,
    seeds: list[int],
) -> list[tuple[int, np.ndarray, np.ndarray, int]]:
    """Train the same configuration under several seeds.

    Returns ``(seed, val_scores, test_scores, best_iteration)`` per seed.

    The seed is used *directly* rather than derived from a model name, so two
    different feature sets run at the same seed share their training randomness.
    That makes the comparison paired on training noise, which D-42 showed is the
    dominant source of variation here — larger than the sampling noise the
    bootstrap captures.

    The binned Dataset is built once and reused: it depends on the features, not
    on the seed, and rebuilding it per seed would triple the runtime.
    """
    X_train, y_train = frames[Split.TRAIN]
    X_val, y_val = frames[Split.VAL]
    X_test, _ = frames[Split.TEST]

    negative, positive = int((y_train == 0).sum()), int((y_train == 1).sum())
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

    results = []
    for seed in seeds:
        resolved = dict(params)
        resolved.setdefault("objective", "binary")
        resolved.setdefault("scale_pos_weight", negative / max(positive, 1))
        resolved["seed"] = seed
        resolved["bagging_seed"] = seed
        resolved["feature_fraction_seed"] = seed
        resolved["verbose"] = -1

        booster = lgb.train(
            resolved,
            train_set,
            num_boost_round=num_boost_round,
            valid_sets=[val_set],
            callbacks=[lgb.early_stopping(early_stopping_rounds, verbose=False)],
        )
        best = booster.best_iteration
        results.append(
            (
                seed,
                booster.predict(X_val[features], num_iteration=best),
                booster.predict(X_test[features], num_iteration=best),
                best,
            )
        )
    return results
