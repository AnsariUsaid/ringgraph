"""Offline (retrospective) features: aggregates over *every* row, future included.

This is the Kaggle-style setting: all transactions are on the table at once and
only the test *labels* are hidden. Nothing here reads a label, so test labels are
never used; it does read the features of rows that come later in time, which a
real-time system cannot. Reported separately from the causal setting.

Three label-free families:
* ``of_fe_``   frequency of each entity value over the whole dataset.
* ``of_agg_``  the winning solutions' per-client aggregates: mean/std of the
               C/D/M/amount columns over all of a client's transactions, and each
               row's deviation from them.
* ``of_g_``    graph structure over the whole dataset: distinct neighbours per
               entity, and the size of the client's connected component when
               clients are joined by a (non-hub) shared device.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from fds import schema
from fds.client_profile import PROFILE_COLUMNS, _numeric
from fds.label_features import _codes, add_device_fingerprints
from fds.relational_features import LABEL_KEYS, PAIRS, entity_codes

FE_PREFIX, AGG_PREFIX, GRAPH_PREFIX = "of_fe_", "of_agg_", "of_g_"
AGG_KEYS = ("uid", "card1")
_DEVICE_MAX_CLIENTS = 50  # a device shared by more clients than this is a hub, not a link


def base_columns() -> list[str]:
    from fds.relational_features import base_columns as rel_columns

    return sorted(set(rel_columns()) | set(PROFILE_COLUMNS) | {"ProductCD", "id_02"})


def _group_stats(codes: np.ndarray, x: np.ndarray):
    """Per-row mean and std of ``x`` over the rows sharing the code (NaN-aware)."""
    ok = codes >= 0
    safe = np.where(ok, codes, 0)
    valid = ok & ~np.isnan(x)
    size = codes.max() + 1
    n = np.bincount(safe[valid], minlength=size)
    s1 = np.bincount(safe[valid], weights=x[valid], minlength=size)
    s2 = np.bincount(safe[valid], weights=x[valid] ** 2, minlength=size)
    cnt = n[safe].astype("float64")
    mean = np.where(ok & (cnt > 0), s1[safe] / np.maximum(cnt, 1), np.nan)
    var = s2[safe] / np.maximum(cnt, 1) - (s1[safe] / np.maximum(cnt, 1)) ** 2
    return mean, np.where(ok & (cnt > 1), np.sqrt(np.maximum(var, 0)), np.nan)


def _component_labels(df: pd.DataFrame, uid: np.ndarray) -> np.ndarray:
    """Component id per client, clients joined through shared non-hub devices."""
    n_uid = uid.max() + 1
    rows, cols, offset = [], [], n_uid
    for column in ("DeviceFP", "DeviceFPOS"):
        dev = _codes(df[column])
        ok = dev >= 0
        pairs = pd.DataFrame({"u": uid[ok], "d": dev[ok]}).drop_duplicates()
        degree = pairs.groupby("d")["u"].transform("size")
        pairs = pairs[(degree >= 2) & (degree <= _DEVICE_MAX_CLIENTS)]
        rows.append(pairs["u"].to_numpy())
        cols.append(pairs["d"].to_numpy() + offset)
        offset += dev.max() + 1
    r, c = np.concatenate(rows), np.concatenate(cols)
    graph = coo_matrix((np.ones(len(r)), (r, c)), shape=(offset, offset))
    return connected_components(graph, directed=False)[1][:n_uid]


def component_ids(df: pd.DataFrame) -> np.ndarray:
    """Per-row id of the client's device-linked component (for prediction smoothing)."""
    df = add_device_fingerprints(df.copy())
    uid = _codes(df[schema.UID])
    return _component_labels(df, uid)[uid]


def build_offline(df: pd.DataFrame) -> pd.DataFrame:
    """``df`` needs ``base_columns()`` plus uid."""
    df = add_device_fingerprints(df.copy())
    codes = entity_codes(df)
    uid = _codes(df[schema.UID])
    t = df[schema.TIME_RAW].to_numpy("int64")
    out: dict[str, np.ndarray] = {}

    for name in set(LABEL_KEYS) | {"uid", "card1", "DeviceInfo"}:
        kc = uid if name == "uid" else codes[name]
        ok = kc >= 0
        safe = np.where(ok, kc, 0)
        out[f"{FE_PREFIX}{name}"] = np.where(ok, np.bincount(safe[ok], minlength=safe.max() + 1)[safe], np.nan)

    values = _numeric(df)
    for key in AGG_KEYS:
        kc = uid if key == "uid" else codes[key]
        for col, x in values.items():
            mean, std = _group_stats(kc, x)
            out[f"{AGG_PREFIX}{key}_{col}_mean"] = mean
            out[f"{AGG_PREFIX}{key}_{col}_dev"] = x - mean
            if key == "uid":
                out[f"{AGG_PREFIX}{key}_{col}_std"] = std

    for key, other in PAIRS:
        kc = uid if key == "uid" else codes[key]
        oc = uid if other == "uid" else codes[other]
        ok = (kc >= 0) & (oc >= 0)
        distinct = pd.DataFrame({"k": kc[ok], "o": oc[ok]}).drop_duplicates().groupby("k").size()
        out[f"{GRAPH_PREFIX}nu_{key}_{other}"] = np.where(kc >= 0, pd.Series(kc).map(distinct).to_numpy(), np.nan)

    day = t / 86_400
    out[f"{GRAPH_PREFIX}uid_span_days"] = (
        pd.Series(day).groupby(uid).transform("max") - pd.Series(day).groupby(uid).transform("min")
    ).to_numpy()
    out[f"{GRAPH_PREFIX}uid_n_txn"] = np.bincount(uid)[uid]
    comp = _component_labels(df, uid)
    rows_per_uid = np.bincount(uid, minlength=uid.max() + 1)
    out[f"{GRAPH_PREFIX}comp_clients"] = np.bincount(comp)[comp][uid]
    out[f"{GRAPH_PREFIX}comp_rows"] = np.bincount(comp, weights=rows_per_uid)[comp][uid]

    table = pd.DataFrame({k: np.asarray(v, dtype="float32") for k, v in out.items()})
    table.insert(0, schema.KEY, df[schema.KEY].to_numpy())
    return table


def smooth_scores(score: np.ndarray, groups: np.ndarray, alpha: float, mode: str = "mean") -> np.ndarray:
    """alpha * own score + (1 - alpha) * the group's mean (or max) score.

    The winners replaced each transaction's score with its client's mean score:
    alpha=0, mode="mean" is that; alpha=1 is no smoothing. ``max`` flags every row of a
    client that has one suspicious row. Group statistics are over every row passed in,
    future included -- the offline setting.
    """
    stat = pd.Series(score).groupby(groups).transform(mode).to_numpy()
    return alpha * score + (1 - alpha) * stat
