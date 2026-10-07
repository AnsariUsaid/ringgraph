"""Risk propagation must not depend on any label that was unconfirmed at the row's time."""

from __future__ import annotations

import numpy as np
import pandas as pd

from fds import schema
from fds.label_features import SECONDS_PER_DAY
from fds.risk_propagation import propagate, rolling_scores

DELAY = 20 * SECONDS_PER_DAY
PARAMS = {"objective": "binary", "verbose": -1, "num_threads": 1, "deterministic": True, "seed": 1,
          "min_data_in_leaf": 5, "num_leaves": 4, "force_row_wise": True}


def _frame(n: int = 900, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    f = rng.normal(size=n)
    y = (rng.random(n) < 1 / (1 + np.exp(-(2 * f - 2.2)))).astype(int)
    return pd.DataFrame(
        {
            schema.KEY: np.arange(n),
            schema.TIME_RAW: np.sort(rng.integers(86_400, 86_400 * 150, n)),
            schema.TARGET: y,
            schema.UID: rng.integers(0, 30, n).astype(str),
            "card1": rng.integers(0, 12, n),
            "addr1": rng.integers(0, 8, n).astype(float),
            "P_emaildomain": rng.choice(["a.com", "b.com"], n),
            "DeviceInfo": rng.choice(["d1", "d2", "d3"], n),
            "id_31": rng.choice(["x", "y"], n),
            "id_33": rng.choice(["1", "2"], n),
            "id_30": rng.choice(["w", "m"], n),
            "f": f,
        }
    )


def _features(df: pd.DataFrame) -> pd.DataFrame:
    t = df[schema.TIME_RAW].to_numpy("int64")
    score = rolling_scores(
        df[["f"]], t, df[schema.TARGET].to_numpy(), categorical=[], params=PARAMS,
        delay_s=DELAY, window_s=10 * SECONDS_PER_DAY, first_start_s=40 * SECONDS_PER_DAY, rounds=20,
    )
    return propagate(df, score)


def test_unconfirmed_labels_cannot_change_a_row():
    df = _frame()
    base = _features(df)
    assert base.filter(like="rq_").notna().any().any()
    for i in (500, 700, 850):
        t = df.loc[i, schema.TIME_RAW]
        unconfirmed = df[schema.TIME_RAW] + DELAY > t
        flipped = df.copy()
        flipped.loc[unconfirmed, schema.TARGET] = 1 - flipped.loc[unconfirmed, schema.TARGET]
        pd.testing.assert_series_equal(base.loc[i], _features(flipped).loc[i], check_names=False)
