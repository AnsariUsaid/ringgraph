"""Relational features: what the entity graph says about a transaction at time t.

The graph is the bipartite graph of transactions and the entities they touch
(card, address, email, device, and crossings of those). Every feature is a
temporal lookup over that graph that sees only rows strictly before ``t`` and
only labels confirmed by ``t`` (``fraud time + delay <= t``). Three families:

* ``rl<D>_``  delayed-label exposure over many keys, counted over all rows with
  the key and over *other clients* only.
* ``rs_``     label-free neighbourhood behaviour: new neighbours on an entity in
  the last day/week (card hopping, device hopping), bursts, gaps, amount against
  the entity's own history.
* ``rp<D>_``  two-hop propagation: how suspicious were the earlier transactions
  that share a key with this one, where "suspicious" is itself the delayed-label
  exposure those transactions had *at their own time*. All labels used were
  therefore confirmed before ``t`` as well.

``tests/test_relational_leakage.py`` pins all three families against a
brute-force reference and by flipping labels that are not yet confirmed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fds import schema
from fds.label_features import (
    _K,
    SECONDS_PER_DAY,
    _codes,
    _count_before,
    _prior_and_confirmed,
    _rate,
    _window_count,
    add_device_fingerprints,
)

# Entity keys. A tuple is a crossing: null in any part makes the key null.
LABEL_KEYS: dict[str, tuple[str, ...]] = {
    "card1": ("card1",),
    "addr1": ("addr1",),
    "pemail": ("P_emaildomain",),
    "remail": ("R_emaildomain",),
    "card_addr": ("card1", "addr1"),
    "card_email": ("card1", "P_emaildomain"),
    "addr_email": ("addr1", "P_emaildomain"),
    "card_dev": ("card1", "DeviceFP"),
    "addr_dev": ("addr1", "DeviceFP"),
    "email_pair": ("P_emaildomain", "R_emaildomain"),
    "card_full": ("card1", "card2", "card3", "card5"),
    "dev": ("DeviceFP",),
    "devos": ("DeviceFPOS",),
}
# Neighbour counting: how many distinct N-entities appear on a K-entity recently.
PAIRS: tuple[tuple[str, str], ...] = (
    ("card1", "addr1"),
    ("card1", "P_emaildomain"),
    ("card1", "DeviceFP"),
    ("card1", "uid"),
    ("DeviceFP", "card1"),
    ("DeviceFP", "uid"),
    ("DeviceFP", "addr1"),
    ("DeviceFP", "P_emaildomain"),
    ("addr1", "card1"),
    ("addr1", "DeviceFP"),
    ("uid", "DeviceFP"),
    ("P_emaildomain", "card1"),
)
ACTIVITY_KEYS = ("card1", "uid", "DeviceFP", "addr1", "P_emaildomain")
PROPAGATE_KEYS = ("DeviceFP", "card1", "addr1", "P_emaildomain", "DeviceInfo")
LABEL_PREFIX, STRUCT_PREFIX, PROP_PREFIX = "rl", "rs_", "rp"
_SUSPICIOUS = 0.10  # smoothed exposure rate above which a past transaction counts as suspicious
_PROP_WINDOW_DAYS = 30
_MIN_HISTORY = 3  # rows of history before an amount z-score is defined


def base_columns() -> list[str]:
    cols = {c for parts in LABEL_KEYS.values() for c in parts}
    cols |= {c for pair in PAIRS for c in pair}
    cols |= set(PROPAGATE_KEYS) | set(ACTIVITY_KEYS)
    cols -= {"uid", "DeviceFP", "DeviceFPOS"}
    return sorted(
        cols
        | {schema.KEY, schema.TIME_RAW, schema.TARGET, schema.AMOUNT, "DeviceInfo", "id_31", "id_33", "id_30"}
    )


def entity_codes(df: pd.DataFrame) -> dict[str, np.ndarray]:
    """Integer code per entity key (-1 = null) for every key used below."""
    codes: dict[str, np.ndarray] = {}

    def code_of(parts: tuple[str, ...]) -> np.ndarray:
        if len(parts) == 1:
            return _codes(df[parts[0]])
        joined = df[parts[0]].astype("string")
        for p in parts[1:]:
            joined = joined + "|" + df[p].astype("string")
        return _codes(joined)

    wanted = {**{k: v for k, v in LABEL_KEYS.items()}}
    for col in {c for pair in PAIRS for c in pair} | set(PROPAGATE_KEYS) | set(ACTIVITY_KEYS):
        wanted.setdefault(col, (col,))
    for name, parts in wanted.items():
        codes[name] = code_of(parts)
    return codes


def _pair_code(key: np.ndarray, uid: np.ndarray) -> np.ndarray:
    pair = pd.factorize(key * (uid.max() + 1) + uid)[0].astype("int64")
    return np.where(key >= 0, pair, -1)


def _sorted_events(codes: np.ndarray, t: np.ndarray, values: np.ndarray | None = None):
    """Events ordered by (code, time) plus prefix sums of ``values`` in that order."""
    ok = np.flatnonzero(codes >= 0)
    packed = codes[ok] * _K + t[ok]
    order = np.argsort(packed, kind="stable")
    ev = packed[order]
    prefix = None
    if values is not None:
        prefix = np.concatenate([[0.0], np.cumsum(values[ok][order], dtype="float64")])
    return ev, prefix


def _window_sum(ev, prefix, codes, t, window_s: int | None):
    """Sum of values over rows with the same code and time in [t - window, t)."""
    ok = codes >= 0
    safe = np.where(ok, codes, 0)
    hi = np.searchsorted(ev, safe * _K + t, "left")
    lo = np.searchsorted(ev, safe * _K + (np.maximum(t - window_s, 0) if window_s else 0), "left")
    return np.where(ok, prefix[hi] - prefix[lo], 0.0), np.where(ok, hi - lo, 0)


def label_exposure(df: pd.DataFrame, codes: dict[str, np.ndarray], delay_days: int):
    """``rl<D>_`` family, plus the per-row stage-1 suspicion used for propagation."""
    t = df[schema.TIME_RAW].to_numpy("int64")
    fraud = df[schema.TARGET].to_numpy() == 1
    delay_s = delay_days * SECONDS_PER_DAY
    uid = _codes(df[schema.UID])
    out: dict[str, np.ndarray] = {}
    rates, n_conf_keys = [], np.zeros(len(df), dtype="int32")
    for name in LABEL_KEYS:
        kc = codes[name]
        prior, conf = _prior_and_confirmed(kc, t, fraud, delay_s)
        pair = _pair_code(kc, uid)
        prior_p, conf_p = _prior_and_confirmed(pair, t, fraud, delay_s)
        cross_conf, cross_prior = conf - conf_p, prior - prior_p
        base = f"{LABEL_PREFIX}{delay_days}_{name}"
        out[f"{base}_all_conf"], out[f"{base}_all_rate"] = conf, _rate(conf, prior)
        out[f"{base}_x_conf"], out[f"{base}_x_rate"] = cross_conf, _rate(cross_conf, cross_prior)
        rates.append(out[f"{base}_x_rate"])
        n_conf_keys += cross_conf > 0
    own_prior, own_conf = _prior_and_confirmed(uid, t, fraud, delay_s)
    own_rate = _rate(own_conf, own_prior)
    out[f"{LABEL_PREFIX}{delay_days}_uid_conf"] = own_conf
    out[f"{LABEL_PREFIX}{delay_days}_uid_rate"] = own_rate
    out[f"{LABEL_PREFIX}{delay_days}_max_rate_x"] = np.max(rates, axis=0)
    out[f"{LABEL_PREFIX}{delay_days}_n_keys_conf_x"] = n_conf_keys
    suspicion = np.maximum(own_rate, out[f"{LABEL_PREFIX}{delay_days}_max_rate_x"])
    return out, suspicion


def structure_features(df: pd.DataFrame, codes: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """``rs_`` family. No labels anywhere in here."""
    t = df[schema.TIME_RAW].to_numpy("int64")
    amount = np.log1p(df[schema.AMOUNT].to_numpy("float64"))
    out: dict[str, np.ndarray] = {}

    for key, other in PAIRS:
        kc, oc = codes[key], codes[other]
        both = (kc >= 0) & (oc >= 0)
        pc = np.where(both, pd.factorize(kc * (oc.max() + 1) + oc)[0], -1).astype("int64")
        # Is this (key, other) pairing new, and how many new pairings did the key see lately?
        prior_pair = _prior_and_confirmed(pc, t, np.zeros(len(t), dtype=bool), 0)[0]
        out[f"rs_{key}_{other}_isnew"] = np.where(both, (prior_pair == 0).astype("float32"), np.nan)
        idx = np.flatnonzero(both)
        order = np.lexsort((t[idx], pc[idx]))
        s_pc, s_t, s_k = pc[idx][order], t[idx][order], kc[idx][order]
        first = np.concatenate([[True], s_pc[1:] != s_pc[:-1]])
        ev = np.sort(s_k[first] * _K + s_t[first])
        for label, window in (("1d", SECONDS_PER_DAY), ("7d", 7 * SECONDS_PER_DAY)):
            safe = np.where(kc >= 0, kc, 0)
            tw = np.maximum(t - window, 0)
            n = _count_before(ev, safe, t, inclusive=False) - _count_before(ev, safe, tw, inclusive=False)
            out[f"rs_{key}_new_{other}_{label}"] = np.where(kc >= 0, n, np.nan)

    for key in ACTIVITY_KEYS:
        kc = codes[key]
        valid = kc >= 0
        for label, window in (("1h", 3600), ("1d", SECONDS_PER_DAY), ("7d", 7 * SECONDS_PER_DAY)):
            out[f"rs_{key}_cnt_{label}"] = np.where(valid, _window_count(kc, t, window), np.nan)
        ev, prefix = _sorted_events(kc, t, amount)
        _, p2 = _sorted_events(kc, t, amount**2)
        safe = np.where(valid, kc, 0)
        hi = np.searchsorted(ev, safe * _K + t, "left")
        lo = np.searchsorted(ev, safe * _K, "left")
        n = hi - lo
        s1, s2 = prefix[hi] - prefix[lo], p2[hi] - p2[lo]
        mean = np.where(n > 0, s1 / np.maximum(n, 1), np.nan)
        var = np.where(n > 1, s2 / np.maximum(n, 1) - mean**2, np.nan)
        z = (amount - mean) / np.sqrt(np.maximum(var, 0) + 1e-3)
        out[f"rs_{key}_amt_z"] = np.where(valid & (n >= _MIN_HISTORY), z, np.nan)
        prev = np.clip(hi - 1, 0, max(len(ev) - 1, 0))
        has_prev = valid & (n > 0)
        gap = t - (ev[prev] - safe * _K)
        out[f"rs_{key}_gap_log"] = np.where(has_prev, np.log1p(np.maximum(gap, 0)), np.nan)
    return out


def propagation(df, codes, suspicion: np.ndarray, delay_days: int) -> dict[str, np.ndarray]:
    """``rp<D>_`` family: suspicion of earlier transactions on shared keys, other clients only."""
    t = df[schema.TIME_RAW].to_numpy("int64")
    uid = _codes(df[schema.UID])
    window = _PROP_WINDOW_DAYS * SECONDS_PER_DAY
    high = (suspicion > _SUSPICIOUS).astype("float64")
    out: dict[str, np.ndarray] = {}
    for key in PROPAGATE_KEYS:
        kc = codes[key]
        pair = _pair_code(kc, uid)
        ev_k, pre_s = _sorted_events(kc, t, suspicion)
        _, pre_h = _sorted_events(kc, t, high)
        ev_p, pp_s = _sorted_events(pair, t, suspicion)
        _, pp_h = _sorted_events(pair, t, high)
        s_k, n_k = _window_sum(ev_k, pre_s, kc, t, window)
        h_k, _ = _window_sum(ev_k, pre_h, kc, t, window)
        s_p, n_p = _window_sum(ev_p, pp_s, pair, t, window)
        h_p, _ = _window_sum(ev_p, pp_h, pair, t, window)
        n_x, s_x, h_x = n_k - n_p, s_k - s_p, h_k - h_p
        base = f"{PROP_PREFIX}{delay_days}_{key}"
        out[f"{base}_mean_susp"] = np.where((kc >= 0) & (n_x > 0), s_x / np.maximum(n_x, 1), np.nan)
        out[f"{base}_n_high"] = np.where(kc >= 0, np.round(h_x), np.nan)
    return out


def build_relational(df: pd.DataFrame, delays: tuple[int, ...]) -> pd.DataFrame:
    """All three families. ``df`` needs ``base_columns()`` plus uid."""
    df = add_device_fingerprints(df)
    codes = entity_codes(df)
    out = structure_features(df, codes)
    for d in delays:
        labels, suspicion = label_exposure(df, codes, d)
        out.update(labels)
        out.update(propagation(df, codes, suspicion, d))
    table = pd.DataFrame({k: np.asarray(v, dtype="float32") for k, v in out.items()})
    table.insert(0, schema.KEY, df[schema.KEY].to_numpy())
    return table
