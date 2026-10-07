"""The delayed-label rule: a label may enter a row's features only if it was
confirmed at or before ``t - delay``. This is the claim the whole project rests on."""

from __future__ import annotations

import numpy as np
import pandas as pd

from fds import schema
from fds.label_features import SECONDS_PER_DAY, add_device_fingerprints, build_label_features

DELAY = 30


def _frame(seed: int = 0, n: int = 600) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame(
        {
            schema.KEY: np.arange(n),
            schema.TIME_RAW: np.sort(rng.integers(86_400, 86_400 * 180, n)),
            schema.TARGET: (rng.random(n) < 0.15).astype(int),
            schema.UID: rng.integers(0, 40, n).astype(str),
            "card1": rng.integers(0, 15, n),
            "addr1": rng.integers(0, 15, n),
            "P_emaildomain": rng.choice(["a.com", "b.com", None], n),
            "DeviceInfo": rng.choice(["d1", "d2", "d3", "d4", None], n),
            "id_31": rng.choice(["x", "y"], n),
            "id_33": rng.choice(["1", "2"], n),
            "id_30": rng.choice(["w", "m"], n),
            "id_17": rng.integers(0, 6, n).astype(float),
            "id_19": rng.integers(0, 6, n).astype(float),
            "id_20": rng.integers(0, 6, n).astype(float),
            "id_13": rng.integers(0, 6, n).astype(float),
        }
    )
    return add_device_fingerprints(df)


def _brute(df: pd.DataFrame, i: int, key: str, *, cross: bool) -> int:
    """Confirmed-fraud rows sharing ``key`` with row i, from first principles."""
    row = df.iloc[i]
    if pd.isna(row[key]):
        return 0
    same = df[key] == row[key]
    if cross:
        same &= df[schema.UID] != row[schema.UID]
    known = df[schema.TIME_RAW] + DELAY * SECONDS_PER_DAY <= row[schema.TIME_RAW]
    return int((same & known & (df[schema.TARGET] == 1)).sum())


def test_matches_brute_force_reference():
    df = _frame()
    table = build_label_features(df, DELAY)
    for i in range(0, len(df), 7):
        assert table.loc[i, f"lfc{DELAY}_card1_conf"] == _brute(df, i, "card1", cross=False)
        assert table.loc[i, f"lfc{DELAY}_uid_conf"] == _brute(df, i, schema.UID, cross=False)
        assert table.loc[i, f"lfg{DELAY}_DeviceInfo_conf"] == _brute(df, i, "DeviceInfo", cross=True)
        assert table.loc[i, f"lfg{DELAY}_DeviceFP_conf"] == _brute(df, i, "DeviceFP", cross=True)


def test_future_labels_cannot_change_a_row():
    """Flip every label not yet confirmed at row i; row i's features must not move."""
    df = _frame(seed=1)
    base = build_label_features(df, DELAY)
    for i in (100, 300, 550):
        t = df.loc[i, schema.TIME_RAW]
        future = df[schema.TIME_RAW] + DELAY * SECONDS_PER_DAY > t
        flipped = df.copy()
        flipped.loc[future, schema.TARGET] = 1 - flipped.loc[future, schema.TARGET]
        again = build_label_features(flipped, DELAY)
        pd.testing.assert_series_equal(base.loc[i], again.loc[i], check_names=False)


def test_own_label_is_never_visible():
    df = _frame(seed=2)
    again = df.copy()
    again[schema.TARGET] = 1
    a, b = build_label_features(df, DELAY), build_label_features(again, DELAY)
    first = df[schema.TIME_RAW] < df[schema.TIME_RAW].min() + DELAY * SECONDS_PER_DAY
    cols = [c for c in a.columns if c.endswith("_conf")]
    assert (a.loc[first, cols] == 0).all().all() and (b.loc[first, cols] == 0).all().all()


def test_velocity_uses_only_earlier_other_client_rows_and_no_labels():
    df = _frame(seed=3)
    a = build_label_features(df, DELAY)
    flipped = df.copy()
    flipped[schema.TARGET] = 1 - flipped[schema.TARGET]
    b = build_label_features(flipped, DELAY)
    col = f"lfa{DELAY}_max_cross_velocity_1d"
    pd.testing.assert_series_equal(a[col], b[col])  # label-free
    i = 400
    row = df.iloc[i]
    window = (df[schema.TIME_RAW] >= row[schema.TIME_RAW] - SECONDS_PER_DAY) & (
        df[schema.TIME_RAW] < row[schema.TIME_RAW]
    )
    same = (df["DeviceInfo"] == row["DeviceInfo"]) & (df[schema.UID] != row[schema.UID]) & window
    if not pd.isna(row["DeviceInfo"]):  # max over keys can only be >= any single key's count
        assert a.loc[i, col] >= same.sum()
