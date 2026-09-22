"""Column contract for the IEEE-CIS dataset.

One place that knows what the columns are, what they mean, and which of them a
model is forbidden to see. The deny-list in particular is load-bearing: leaking
``day`` as a feature under a temporal split is catastrophic and is exactly what
the ubiquitous ``df.drop(columns=[target])`` idiom produces.
"""

from __future__ import annotations

TARGET = "isFraud"
KEY = "TransactionID"
TIME_RAW = "TransactionDT"

# --- derived, added during ingest -------------------------------------------
DAY = "day"
D1N = "D1n"  # approximate card registration day: day - D1, constant per card
UID = "uid"

# --- transaction table -------------------------------------------------------
AMOUNT = "TransactionAmt"
PRODUCT = "ProductCD"

CARD_COLS = [f"card{i}" for i in range(1, 7)]
ADDR_COLS = ["addr1", "addr2"]
DIST_COLS = ["dist1", "dist2"]
EMAIL_COLS = ["P_emaildomain", "R_emaildomain"]
C_COLS = [f"C{i}" for i in range(1, 15)]
D_COLS = [f"D{i}" for i in range(1, 16)]
M_COLS = [f"M{i}" for i in range(1, 10)]
V_COLS = [f"V{i}" for i in range(1, 340)]

# --- identity table ----------------------------------------------------------
# id_01..id_38 split by storage type. The competition's data description calls
# id_12..id_38 categorical, but only some of them are actually string-valued;
# the rest are numeric codes and are cheaper left numeric.
ID_NUMERIC_COLS = [
    *[f"id_{i:02d}" for i in range(1, 12)],
    "id_13",
    "id_14",
    *[f"id_{i:02d}" for i in range(17, 23)],
    "id_24",
    "id_25",
    "id_26",
    "id_32",
]
ID_STRING_COLS = [
    "id_12",
    "id_15",
    "id_16",
    "id_23",
    "id_27",
    "id_28",
    "id_29",
    "id_30",  # operating system
    "id_31",  # browser
    "id_33",  # screen resolution, e.g. "1920x1080"
    "id_34",
    "id_35",
    "id_36",
    "id_37",
    "id_38",
]
DEVICE_COLS = ["DeviceType", "DeviceInfo"]

# --- dtype planning ----------------------------------------------------------
# Stored as strings, so genuinely category dtype.
STRING_CATEGORICAL = [
    PRODUCT,
    "card4",
    "card6",
    *EMAIL_COLS,
    *M_COLS,
    *ID_STRING_COLS,
    *DEVICE_COLS,
]

# Numeric on disk but nominal in meaning — identifiers, not quantities. Kept
# numeric for memory, but never treated as ordered by feature engineering.
NOMINAL_NUMERIC = ["card1", "card2", "card3", "card5", *ADDR_COLS]

# Everything genuinely continuous. Downcast to float32: the V block alone is 339
# columns, and float64 over 590k rows costs roughly 1.6GB for no added precision.
FLOAT32_COLS = [AMOUNT, *DIST_COLS, *C_COLS, *D_COLS, *V_COLS, *ID_NUMERIC_COLS, "card3", "card5"]

# --- graph entities ----------------------------------------------------------
# plan.md §Part 3. The attribute each node type is built from.
ENTITY_SOURCE_COLUMNS: dict[str, str] = {
    "Card": "card1",
    "Address": "addr1",
    "EmailDomain": "P_emaildomain",
    "Device": "DeviceInfo",
    "Browser": "id_31",
    "Screen": "id_33",
}

# --- the deny-list -----------------------------------------------------------
# Bookkeeping and provenance columns that must never reach a model matrix.
# ``day`` and ``TransactionDT`` encode position in the temporal split directly;
# ``uid`` is the entity fraud is clustered on by construction (Trap A); the
# snapshot columns are Trap B provenance. ``D1n`` is excluded too: it is a uid
# component and a linear function of ``day``, so it reintroduces temporal
# position through the back door. Raw ``D1`` (days since the card began) is a
# genuine feature and stays.
#
# ``has_structure`` is denied for the same reason, measured rather than assumed:
# it runs 0.34 in train against 0.51 in test, because expanding-window snapshots
# mean later transactions are far more likely to have graph history. That makes
# it partly a clock, and a model that leans on it meets a different distribution
# at test time. The NaN pattern in the structural columns carries some of the
# same information, which is exactly why the comparison must also be reported on
# the subpopulation where every row has structure (D-38).
FEATURE_DENY_LIST: frozenset[str] = frozenset(
    {
        KEY,
        TARGET,
        TIME_RAW,
        DAY,
        UID,
        D1N,
        "split",
        "snapshot_id",
        "end_day_exclusive",
        "max_source_day",
        "n_source_txns",
        "source_txn_hash",
        "has_structure",
    }
)


def assert_no_denied_features(columns: list[str]) -> None:
    """Raise if a model feature list contains a forbidden column.

    Deliberately not an ``assert``: ``python -O`` strips those, and a leak guard
    that can silently vanish is not a guard (D-08).
    """
    denied = sorted(set(columns) & FEATURE_DENY_LIST)
    if denied:
        raise ValueError(
            f"feature list contains denied columns {denied}. These encode the "
            f"target, the temporal position, or snapshot provenance; including "
            f"any of them invalidates the temporal split."
        )


def transaction_columns() -> list[str]:
    """Columns expected in ``train_transaction.csv``, in file order."""
    return [
        KEY,
        TARGET,
        TIME_RAW,
        AMOUNT,
        PRODUCT,
        *CARD_COLS,
        *ADDR_COLS,
        *DIST_COLS,
        *EMAIL_COLS,
        *C_COLS,
        *D_COLS,
        *M_COLS,
        *V_COLS,
    ]


def identity_columns() -> list[str]:
    """Columns expected in ``train_identity.csv``."""
    ids = sorted(set(ID_NUMERIC_COLS) | set(ID_STRING_COLS))
    return [KEY, *ids, *DEVICE_COLS]
