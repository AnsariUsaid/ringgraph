"""Risk propagation: what the *earlier* transactions on a shared entity looked like.

Labels arrive late, so most recent activity on a card or device is unlabelled. A
stage-1 model scores every transaction, and a row then inherits the scores of the
earlier transactions that share an entity with it (message passing over the same
entity graph, but with model risk instead of confirmed labels). This reaches fraud
that no confirmed label links to: bursts, card testing, a device warming up.

No label is used beyond what stage 1 may know. Window k is scored by a model fit
only on rows whose label had matured by the window's start (``time + delay <=
start``), so a score computed at time ``t`` never depends on a label the bank
could not yet have. ``tests/test_risk_leakage.py`` pins this by flipping labels.
"""

from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd

from fds import schema
from fds.label_features import SECONDS_PER_DAY, _codes, add_device_fingerprints
from fds.relational_features import _pair_code, _sorted_events, _window_sum

PREFIX = "rq_"
KEYS = ("card1", "uid", "DeviceFP", "addr1", "P_emaildomain")
CROSS_KEYS = ("DeviceFP", "addr1")
WINDOWS = (("1h", 3600), ("1d", SECONDS_PER_DAY), ("7d", 7 * SECONDS_PER_DAY))
HIGH = 0.3  # a stage-1 probability above this counts as "looks risky"
_MIN_TRAIN_POSITIVES = 50


def rolling_scores(
    X: pd.DataFrame,
    t: np.ndarray,
    y: np.ndarray,
    *,
    categorical: list[str],
    params: dict,
    delay_s: int,
    window_s: int,
    first_start_s: int,
    rounds: int,
) -> np.ndarray:
    """Out-of-time stage-1 score per row; NaN before the first window or without enough labels."""
    scores = np.full(len(t), np.nan)
    start = first_start_s
    while start <= t.max():
        in_window = (t >= start) & (t < start + window_s)
        mature = t + delay_s <= start
        if in_window.any() and y[mature].sum() >= _MIN_TRAIN_POSITIVES:
            booster = lgb.train(
                params,
                lgb.Dataset(X[mature], label=y[mature], categorical_feature=categorical),
                num_boost_round=rounds,
            )
            scores[in_window] = booster.predict(X[in_window])
            print(f"  window from day {start / SECONDS_PER_DAY:5.0f}: trained on {int(mature.sum()):>7,} rows, scored {int(in_window.sum()):>6,}", flush=True)
        start += window_s
    return scores


def propagate(df: pd.DataFrame, score: np.ndarray) -> pd.DataFrame:
    """``rq_`` features from a per-row stage-1 score. ``df`` needs KEY, TIME_RAW, uid and key columns."""
    df = add_device_fingerprints(df.copy())
    t = df[schema.TIME_RAW].to_numpy("int64")
    uid = _codes(df[schema.UID])
    valid = (~np.isnan(score)).astype("float64")
    s = np.nan_to_num(score)
    high = ((s > HIGH) & (valid > 0)).astype("float64")
    out: dict[str, np.ndarray] = {}
    for key in KEYS:
        kc = _codes(df[key])
        variants = {"all": kc}
        if key in CROSS_KEYS:
            variants["x"] = None  # filled below as all minus own-client
        pair = _pair_code(kc, uid)
        evk, ps = _sorted_events(kc, t, s)
        _, pv = _sorted_events(kc, t, valid)
        _, ph = _sorted_events(kc, t, high)
        evp, pps = _sorted_events(pair, t, s)
        _, ppv = _sorted_events(pair, t, valid)
        _, pph = _sorted_events(pair, t, high)
        for label, window in WINDOWS:
            sum_s, _ = _window_sum(evk, ps, kc, t, window)
            n_v, _ = _window_sum(evk, pv, kc, t, window)
            n_h, _ = _window_sum(evk, ph, kc, t, window)
            for kind in variants:
                if kind == "x":
                    ps_x, _ = _window_sum(evp, pps, pair, t, window)
                    pv_x, _ = _window_sum(evp, ppv, pair, t, window)
                    ph_x, _ = _window_sum(evp, pph, pair, t, window)
                    a, b, c = sum_s - ps_x, n_v - pv_x, n_h - ph_x
                else:
                    a, b, c = sum_s, n_v, n_h
                name = f"{PREFIX}{key}_{kind}_{label}"
                out[f"{name}_mean"] = np.where((kc >= 0) & (b > 0.5), a / np.maximum(b, 1), np.nan)
                out[f"{name}_nhigh"] = np.where(kc >= 0, np.round(c), np.nan)
    table = pd.DataFrame({k: np.asarray(v, dtype="float32") for k, v in out.items()})
    table.insert(0, schema.KEY, df[schema.KEY].to_numpy())
    return table
