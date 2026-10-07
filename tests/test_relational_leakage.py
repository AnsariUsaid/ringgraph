"""Relational features obey the same rule as the delayed-label ones: at row i they may
use only rows strictly before i, and labels confirmed by i's time."""

from __future__ import annotations

import numpy as np
import pandas as pd

from fds import schema
from fds.label_features import SECONDS_PER_DAY
from fds.relational_features import build_relational

DELAYS = (30,)
D = 30


def _frame(seed: int = 0, n: int = 700) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    pick = lambda vals, p=None: rng.choice(vals, n, p=p)  # noqa: E731
    return pd.DataFrame(
        {
            schema.KEY: np.arange(n),
            schema.TIME_RAW: np.sort(rng.integers(86_400, 86_400 * 180, n)),
            schema.TARGET: (rng.random(n) < 0.15).astype(int),
            schema.AMOUNT: rng.lognormal(3, 1, n),
            schema.UID: rng.integers(0, 40, n).astype(str),
            "card1": rng.integers(0, 15, n),
            "card2": rng.integers(0, 3, n).astype(float),
            "card3": rng.integers(0, 2, n).astype(float),
            "card5": rng.integers(0, 2, n).astype(float),
            "addr1": rng.integers(0, 10, n).astype(float),
            "P_emaildomain": pick(["a.com", "b.com", None]),
            "R_emaildomain": pick(["a.com", "c.com", None]),
            "DeviceInfo": pick(["d1", "d2", "d3", None]),
            "id_31": pick(["x", "y"]),
            "id_33": pick(["1", "2"]),
            "id_30": pick(["w", "m"]),
        }
    )


def _label_cols(table):
    return [c for c in table.columns if c.startswith(("rl", "rp"))]


def test_unconfirmed_labels_cannot_change_a_row():
    df = _frame()
    base = build_relational(df, DELAYS)
    for i in (150, 400, 650):
        t = df.loc[i, schema.TIME_RAW]
        unconfirmed = df[schema.TIME_RAW] + D * SECONDS_PER_DAY > t
        flipped = df.copy()
        flipped.loc[unconfirmed, schema.TARGET] = 1 - flipped.loc[unconfirmed, schema.TARGET]
        again = build_relational(flipped, DELAYS)
        pd.testing.assert_series_equal(base.loc[i], again.loc[i], check_names=False)


def test_structure_family_is_label_free():
    df = _frame(seed=1)
    flipped = df.assign(**{schema.TARGET: 1 - df[schema.TARGET]})
    a, b = build_relational(df, DELAYS), build_relational(flipped, DELAYS)
    cols = [c for c in a.columns if c.startswith("rs_")]
    assert cols
    pd.testing.assert_frame_equal(a[cols], b[cols])


def test_activity_and_amount_match_brute_force():
    df = _frame(seed=2)
    table = build_relational(df, DELAYS)
    amt = np.log1p(df[schema.AMOUNT])
    for i in range(10, len(df), 37):
        row = df.iloc[i]
        t = row[schema.TIME_RAW]
        before = df[schema.TIME_RAW] < t
        same = df["card1"] == row["card1"]
        in_day = before & same & (df[schema.TIME_RAW] >= t - SECONDS_PER_DAY)
        assert table.loc[i, "rs_card1_cnt_1d"] == in_day.sum()
        hist = amt[before & same]
        if len(hist) >= 3:
            z = (amt[i] - hist.mean()) / np.sqrt(max(hist.var(ddof=0), 0) + 1e-3)
            assert np.isclose(table.loc[i, "rs_card1_amt_z"], z, atol=1e-2)
        else:
            assert np.isnan(table.loc[i, "rs_card1_amt_z"])


def test_matured_rate_matches_brute_force():
    df = _frame(seed=4)
    table = build_relational(df, DELAYS)
    for i in range(20, len(df), 41):
        row = df.iloc[i]
        t = row[schema.TIME_RAW]
        mature = df[schema.TIME_RAW] <= t - D * SECONDS_PER_DAY
        same = df["card1"] == row["card1"]
        n, f = (mature & same).sum(), (mature & same & (df[schema.TARGET] == 1)).sum()
        assert np.isclose(table.loc[i, f"rl{D}_card1_all_mrate"], (f + 0.035 * 20) / (n + 20), atol=1e-5)
