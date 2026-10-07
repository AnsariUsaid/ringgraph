"""Client profile uses only strictly earlier rows of the same entity, and no labels."""

from __future__ import annotations

import numpy as np
import pandas as pd

from fds import schema
from fds.client_profile import PROFILE_COLUMNS, build_profile


def _frame(n: int = 500, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    cols = {c: rng.normal(size=n).astype("float32") for c in PROFILE_COLUMNS if c not in schema.M_COLS}
    cols.update({c: rng.choice(["T", "F", None], n) for c in schema.M_COLS})
    return pd.DataFrame(
        {
            schema.KEY: np.arange(n),
            schema.TIME_RAW: np.sort(rng.integers(86_400, 86_400 * 100, n)),
            schema.AMOUNT: rng.lognormal(3, 1, n).astype("float32"),
            schema.UID: rng.integers(0, 25, n).astype(str),
            "card1": rng.integers(0, 10, n),
            **cols,
        }
    )


def test_mean_and_std_match_brute_force_and_ignore_the_future():
    df = _frame()
    table = build_profile(df)
    for i in range(30, len(df), 29):
        row = df.iloc[i]
        hist = df[(df[schema.UID] == row[schema.UID]) & (df[schema.TIME_RAW] < row[schema.TIME_RAW])]
        x = hist["C1"].astype("float64")
        if len(x) >= 2:
            assert np.isclose(table.loc[i, "cp_uid_C1_mean"], x.mean(), atol=1e-4)
            assert np.isclose(table.loc[i, "cp_uid_C1_std"], x.std(ddof=0), atol=1e-3)
            assert np.isclose(table.loc[i, "cp_uid_C1_dev"], row["C1"] - x.mean(), atol=1e-4)
        else:
            assert np.isnan(table.loc[i, "cp_uid_C1_mean"])
    # Scrambling every row after i must not move row i.
    i = 250
    later = df.copy()
    later.loc[later.index > i, "C1"] = 99.0
    assert build_profile(later).loc[i, "cp_uid_C1_mean"] == table.loc[i, "cp_uid_C1_mean"]
