"""Delayed-label ("dynamic knowledge") features.

A fraud label only becomes usable ``delay`` days after the fraudulent transaction
(the chargeback delay). For a transaction at time ``t`` and a shared key value
``k`` the features count transactions that carry ``k`` and were *confirmed* fraud
by ``t``:

    fraud txn f is known at t  <=>  f.time + delay <= t

Because ``delay > 0`` a row can never see its own label, and a row never sees a
label that the bank could not yet have had. ``tests/test_label_leakage.py`` pins
this against a brute-force reference and by flipping future labels.

Two families, so the graph has to beat a tabular control on its own:

* control (``lfc``): keys the tabular model could in principle target-encode
  (card1, addr1, email domain, reconstructed client).
* graph (``lfg``): device attributes. Exposure is counted over *other* clients
  that share the key, i.e. a client-to-client link carrying confirmed fraud.
  No degree ceiling: rarity is expressed by the smoothed rate and by the
  rare-key aggregates instead of dropping hubs.

Everything is a sorted-array lookup, so a table for 590k rows takes seconds.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fds import schema

DELAYS = (7, 14, 30, 60, 90)  # 7/14: sensitivity if the bank confirms fraud faster
CONTROL_KEYS = ("card1", "addr1", "P_emaildomain", "uid")
GRAPH_KEYS = (
    "DeviceInfo",
    "id_31",
    "id_33",
    "id_30",
    "id_17",
    "id_19",
    "id_20",
    "id_13",
    "DeviceFP",  # DeviceInfo|id_31|id_33
    "DeviceFPOS",  # id_30|id_31|id_33|DeviceInfo
)
CONTROL_PREFIX = "lfc"
GRAPH_PREFIX = "lfg"
AGG_PREFIX = "lfa"  # compact cross-key aggregates (the M3 candidate set)

SECONDS_PER_DAY = 86_400
_K = 1 << 26  # > max TransactionDT + 90 days (~2.4e7), keeps (code, time) packable
_RARITY = (5, 20, 50, 200)  # a key with <= this many other-client txns before t is "rare"
_BASE_RATE = 0.035  # fixed shrinkage target; a constant, not estimated from labels
_SHRINK = 20


def _codes(series: pd.Series) -> np.ndarray:
    return pd.factorize(series)[0].astype("int64")  # -1 for null


def _count_before(events: np.ndarray, codes: np.ndarray, t: np.ndarray, *, inclusive: bool):
    """Per row: events with the same code and time < t (or <= t if inclusive)."""
    side = "right" if inclusive else "left"
    return np.searchsorted(events, codes * _K + t, side) - np.searchsorted(
        events, codes * _K, "left"
    )


def _prior_and_confirmed(
    codes: np.ndarray, t: np.ndarray, fraud: np.ndarray, delay_s: int
) -> tuple[np.ndarray, np.ndarray]:
    """(transactions strictly before t, fraud confirmed by t) sharing the code."""
    ok = codes >= 0
    prior_ev = np.sort(codes[ok] * _K + t[ok])
    conf_ev = np.sort(codes[ok & fraud] * _K + t[ok & fraud] + delay_s)
    safe = np.where(ok, codes, 0)
    prior = np.where(ok, _count_before(prior_ev, safe, t, inclusive=False), 0)
    conf = np.where(ok, _count_before(conf_ev, safe, t, inclusive=True), 0)
    return prior, conf


def _window_count(codes: np.ndarray, t: np.ndarray, window_s: int) -> np.ndarray:
    """Per row: transactions with the same code in [t - window, t)."""
    ok = codes >= 0
    ev = np.sort(codes[ok] * _K + t[ok])
    safe = np.where(ok, codes, 0)
    tw = np.maximum(t - window_s, 0)
    return np.where(ok, _count_before(ev, safe, t, inclusive=False) - _count_before(ev, safe, tw, inclusive=False), 0)


def _rate(conf: np.ndarray, prior: np.ndarray) -> np.ndarray:
    return (conf + _BASE_RATE * _SHRINK) / (prior + _SHRINK)


def build_label_features(df: pd.DataFrame, delay_days: int) -> pd.DataFrame:
    """Feature table for one delay. ``df`` needs KEY, TIME_RAW, TARGET, uid and key columns.

    Returns ``TransactionID`` plus ``lfc<D>_*`` and ``lfg<D>_*`` columns, float32.
    """
    t = df[schema.TIME_RAW].to_numpy("int64")
    fraud = df[schema.TARGET].to_numpy() == 1
    delay_s = delay_days * SECONDS_PER_DAY
    uid_code = _codes(df[schema.UID])

    out: dict[str, np.ndarray] = {}

    for key in CONTROL_KEYS:
        prior, conf = _prior_and_confirmed(_codes(df[key]), t, fraud, delay_s)
        name = f"{CONTROL_PREFIX}{delay_days}_{key}"
        out[f"{name}_conf"] = conf
        out[f"{name}_rate"] = _rate(conf, prior)

    n = len(df)
    exposed = {r: np.zeros(n, dtype="int32") for r in _RARITY}
    max_rate = {r: np.zeros(n) for r in (50, 200)}
    total_cross_conf = np.zeros(n, dtype="int32")
    max_vel = np.zeros(n)
    n_active = np.zeros(n, dtype="int32")
    for key in GRAPH_KEYS:
        kc = _codes(df[key])
        prior_k, conf_k = _prior_and_confirmed(kc, t, fraud, delay_s)
        # Same key AND same client: subtracting it leaves only *other* clients.
        pair = pd.factorize(kc * (uid_code.max() + 1) + uid_code)[0].astype("int64")
        pair = np.where(kc >= 0, pair, -1)
        prior_p, conf_p = _prior_and_confirmed(pair, t, fraud, delay_s)
        cross_conf, cross_prior = conf_k - conf_p, prior_k - prior_p
        rate = _rate(cross_conf, cross_prior)

        name = f"{GRAPH_PREFIX}{delay_days}_{key}"
        out[f"{name}_conf"] = cross_conf
        out[f"{name}_rate"] = rate

        # Label-free coordination: other clients' transactions on this key in the last day.
        vel = _window_count(kc, t, SECONDS_PER_DAY) - _window_count(pair, t, SECONDS_PER_DAY)
        rare_key = (cross_prior <= 200) & (kc >= 0)
        max_vel = np.maximum(max_vel, np.where(rare_key, vel, 0))
        n_active += rare_key & (vel > 0)
        for r in _RARITY:
            exposed[r] += (cross_conf > 0) & (cross_prior <= r)
        for r in max_rate:
            max_rate[r] = np.maximum(max_rate[r], np.where((cross_conf > 0) & (cross_prior <= r), rate, 0.0))
        total_cross_conf += cross_conf

    agg = f"{AGG_PREFIX}{delay_days}_"
    for r in _RARITY:
        out[f"{agg}n_exposed_le{r}"] = exposed[r]
    for r in max_rate:
        out[f"{agg}max_rate_le{r}"] = max_rate[r]
    out[agg + "total_cross_conf"] = total_cross_conf
    out[agg + "max_cross_velocity_1d"] = max_vel
    out[agg + "n_keys_active_1d"] = n_active

    table = pd.DataFrame({k: v.astype("float32") for k, v in out.items()})
    table.insert(0, schema.KEY, df[schema.KEY].to_numpy())
    return table


def add_device_fingerprints(df: pd.DataFrame) -> pd.DataFrame:
    """Composite device keys; a null in any part makes the whole key null."""
    parts = {c: df[c].astype("string") for c in ("DeviceInfo", "id_31", "id_33", "id_30")}
    df["DeviceFP"] = parts["DeviceInfo"] + "|" + parts["id_31"] + "|" + parts["id_33"]
    df["DeviceFPOS"] = parts["id_30"] + "|" + df["DeviceFP"]
    return df


def label_feature_columns(df: pd.DataFrame, delay_days: int, family: str) -> list[str]:
    prefix = f"{family}{delay_days}_"
    return [c for c in df.columns if c.startswith(prefix)]


def needed_base_columns() -> list[str]:
    keys = {k for k in (*CONTROL_KEYS, *GRAPH_KEYS) if k not in ("uid", "DeviceFP", "DeviceFPOS")}
    return sorted({schema.KEY, schema.TIME_RAW, schema.TARGET, "DeviceInfo", "id_31", "id_33", "id_30", *keys})
