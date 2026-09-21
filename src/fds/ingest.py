"""Build the immutable base frame from the two Kaggle CSVs.

This is written once and never rewritten (D-10). Everything downstream reads it,
so it carries only what is recipe-independent: the raw columns with their dtypes
fixed, plus ``day`` and ``D1n``, which are deterministic per-row functions of raw
values. uid variants live in separate narrow key tables rather than as extra
columns here, because three recipes would otherwise mean three 400-column frames
that can drift apart.

Dtypes are set at parse time rather than after. The V block alone is 339 columns;
read as float64 over 590k rows it costs roughly 1.6GB for no added precision.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from fds import schema
from fds.entities import add_d1n
from fds.splits import day_from_transaction_dt, verify_day_range

BASE_SCHEMA_VERSION = 1


def build_dtype_map() -> dict[str, Any]:
    """Per-column dtypes for ``read_csv``.

    Nominal-numeric columns (card1, addr1, ...) stay numeric for memory but are
    identifiers, not quantities — ``schema.NOMINAL_NUMERIC`` records that so no
    downstream code treats them as ordered.
    """
    dtypes: dict[str, Any] = {schema.KEY: "int32", schema.TARGET: "int8"}
    dtypes[schema.TIME_RAW] = "int64"
    for col in schema.FLOAT32_COLS:
        dtypes[col] = "float32"
    for col in schema.STRING_CATEGORICAL:
        dtypes[col] = "category"
    for col in ("card1", "card2", *schema.ADDR_COLS):
        dtypes[col] = "float32"  # nullable in the source; kept float to admit NaN
    return dtypes


def load_raw(transaction_csv: Path | str, identity_csv: Path | str) -> pd.DataFrame:
    """Read and left-join the two source tables on ``TransactionID``.

    The join is a left join from transactions: identity attributes cover only
    about a quarter of rows (plan.md §Part 2), and the missing three quarters are
    a fact about the data, not rows to drop.
    """
    dtypes = build_dtype_map()
    transactions = pd.read_csv(transaction_csv, dtype=dtypes, low_memory=False)
    identity = pd.read_csv(identity_csv, dtype=dtypes, low_memory=False)

    # The public test-set identity file uses hyphens (id-01) where the train file
    # uses underscores (id_01). Normalise so the same schema applies to both.
    identity = identity.rename(columns=lambda c: c.replace("-", "_"))

    merged = transactions.merge(identity, on=schema.KEY, how="left", validate="one_to_one")
    return merged


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Attach ``day`` and ``D1n`` and verify the day index spans what we expect."""
    out = df.copy()
    out[schema.DAY] = day_from_transaction_dt(out[schema.TIME_RAW])
    verify_day_range(out[schema.DAY])
    return add_d1n(out)


def identity_coverage(df: pd.DataFrame) -> dict[str, float]:
    """How much of the graph can carry device attributes at all.

    plan.md calls this out explicitly: device-linked analysis runs on a minority
    of the graph, and that must be an examined decision rather than an
    unexamined hole.
    """
    present = df["DeviceInfo"].notna() if "DeviceInfo" in df.columns else pd.Series(False)
    any_identity = df[[c for c in schema.ID_NUMERIC_COLS if c in df.columns]].notna().any(axis=1)
    return {
        "rows": len(df),
        "any_identity_share": float(any_identity.mean()),
        "deviceinfo_share": float(present.mean()),
        "fraud_rate": float(df[schema.TARGET].mean()),
    }
