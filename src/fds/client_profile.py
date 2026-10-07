"""Causal client behaviour profile.

The IEEE-CIS winners aggregated C/D/M/amount features per reconstructed client
(card1, addr1, day - D1) -- over the whole dataset, future included. That cannot be
done when fraud must be caught in real time, so this is the causal version: for
each transaction, the mean (and std) of the *earlier* transactions of the same
entity, and how far this transaction sits from that history.

A client's fraud is usually a departure from their own pattern, which is a
relational signal a row-level model cannot see.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fds import schema
from fds.label_features import _K, _codes

PREFIX = "cp_"
PROFILE_COLUMNS: tuple[str, ...] = (
    *schema.C_COLS,
    "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "D11", "D15",
    *schema.M_COLS,
    "V127", "V136", "V307", "V309", "V314", "V320",
    "dist1", "id_02",
)
KEYS = ("uid", "card1")  # uid: full profile with std; card1: mean and deviation only
_MIN_HISTORY = 2


def base_columns() -> list[str]:
    return sorted({schema.KEY, schema.TIME_RAW, schema.AMOUNT, "card1", *PROFILE_COLUMNS})


def _numeric(df: pd.DataFrame) -> dict[str, np.ndarray]:
    out = {c: df[c].astype("float64").to_numpy() for c in PROFILE_COLUMNS if c not in schema.M_COLS}
    for c in schema.M_COLS:  # T/F flags -> 1/0, missing stays missing
        out[c] = df[c].astype("string").map({"T": 1.0, "F": 0.0}).astype("float64").to_numpy()
    amount = df[schema.AMOUNT].to_numpy("float64")
    out["log_amt"] = np.log1p(amount)
    out["cents"] = np.round((amount - np.floor(amount)) * 1000)  # the competition's "cents" trick
    return out


def build_profile(df: pd.DataFrame) -> pd.DataFrame:
    """``df`` needs ``base_columns()`` plus uid. Returns TransactionID + ``cp_`` columns (float32)."""
    t = df[schema.TIME_RAW].to_numpy("int64")
    values = _numeric(df)
    out: dict[str, np.ndarray] = {}
    for key in KEYS:
        kc = _codes(df[key])
        ok = np.flatnonzero(kc >= 0)
        packed = kc[ok] * _K + t[ok]
        order = np.argsort(packed, kind="stable")
        ev = packed[order]
        safe = np.where(kc >= 0, kc, 0)
        hi = np.searchsorted(ev, safe * _K + t, "left")  # strictly earlier rows of the same entity
        lo = np.searchsorted(ev, safe * _K, "left")
        for name, x in values.items():
            xs = x[ok][order]
            valid = ~np.isnan(xs)
            n = np.concatenate([[0], np.cumsum(valid)])
            s1 = np.concatenate([[0.0], np.cumsum(np.where(valid, xs, 0.0))])
            cnt = (n[hi] - n[lo]).astype("float64")
            mean = np.where(cnt >= _MIN_HISTORY, (s1[hi] - s1[lo]) / np.maximum(cnt, 1), np.nan)
            mean = np.where(kc >= 0, mean, np.nan)
            base = f"{PREFIX}{key}_{name}"
            out[f"{base}_mean"] = mean
            out[f"{base}_dev"] = x - mean
            if key == "uid":
                s2 = np.concatenate([[0.0], np.cumsum(np.where(valid, xs * xs, 0.0))])
                var = (s2[hi] - s2[lo]) / np.maximum(cnt, 1) - ((s1[hi] - s1[lo]) / np.maximum(cnt, 1)) ** 2
                out[f"{base}_std"] = np.where(cnt >= _MIN_HISTORY, np.sqrt(np.maximum(var, 0)), np.nan)
    table = pd.DataFrame({k: np.asarray(v, dtype="float32") for k, v in out.items()})
    table.insert(0, schema.KEY, df[schema.KEY].to_numpy())
    return table
