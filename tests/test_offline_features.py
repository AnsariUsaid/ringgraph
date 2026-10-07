"""Offline features read no label, and compute what they say they compute."""

from __future__ import annotations

import numpy as np
import pandas as pd

from fds import schema
from fds.client_profile import PROFILE_COLUMNS
from fds.offline_features import build_offline, component_ids, smooth_scores


def _frame(seed: int = 0, n: int = 600) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    cols = {c: rng.normal(size=n).astype("float32") for c in PROFILE_COLUMNS if not c.startswith("M")}
    cols.update({f"M{i}": rng.choice(["T", "F", None], n) for i in range(1, 10)})
    return pd.DataFrame(
        {
            schema.KEY: np.arange(n),
            schema.TIME_RAW: np.sort(rng.integers(86_400, 86_400 * 100, n)),
            schema.TARGET: (rng.random(n) < 0.1).astype(int),
            schema.AMOUNT: rng.lognormal(3, 1, n).astype("float32"),
            schema.UID: rng.integers(0, 25, n).astype(str),
            "card1": rng.integers(0, 10, n),
            "card2": rng.integers(0, 3, n).astype(float),
            "card3": rng.integers(0, 2, n).astype(float),
            "card5": rng.integers(0, 2, n).astype(float),
            "ProductCD": rng.choice(["W", "C"], n),
            "P_emaildomain": rng.choice(["a.com", "b.com", None], n),
            "R_emaildomain": rng.choice(["a.com", None], n),
            "addr1": rng.integers(0, 8, n).astype(float),
            "DeviceInfo": rng.choice(["d1", "d2", "d3", "d4", None], n),
            "id_31": rng.choice(["x", "y"], n),
            "id_33": rng.choice(["1", "2"], n),
            "id_30": rng.choice(["w", "m"], n),
            **cols,
        }
    )


def test_label_free_and_matches_brute_force():
    df = _frame()
    a = build_offline(df)
    b = build_offline(df.assign(**{schema.TARGET: 1 - df[schema.TARGET]}))
    pd.testing.assert_frame_equal(a, b)
    for i in range(0, len(df), 53):
        row = df.iloc[i]
        same = df[schema.UID] == row[schema.UID]
        assert a.loc[i, "of_fe_uid"] == same.sum()
        assert np.isclose(a.loc[i, "of_agg_uid_C1_mean"], df.loc[same, "C1"].mean(), atol=1e-4)
        assert a.loc[i, "of_g_uid_n_txn"] == same.sum()


def test_smoothing_endpoints():
    s = np.array([0.0, 1.0, 0.2, 0.4])
    g = np.array([0, 0, 1, 1])
    assert np.allclose(smooth_scores(s, g, 1.0), s)
    assert np.allclose(smooth_scores(s, g, 0.0), [0.5, 0.5, 0.3, 0.3])


def test_a_client_sits_in_one_component():
    df = _frame(seed=2)
    comp = component_ids(df)
    assert len(comp) == len(df)
    assert (pd.Series(comp).groupby(df[schema.UID].to_numpy()).nunique() == 1).all()
