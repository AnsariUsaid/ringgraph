"""Expanding-window graph snapshots — the Trap B machinery.

plan.md's rule: a structural feature attached to a transaction at time *t* may
only be computed from the graph restricted to transactions strictly before *t*.
This module is where that rule is made true, and it sits at the top level of the
package rather than inside ``features/`` because it is the intellectual core of
the project, not an implementation detail.

Three layers, because one assertion is not enough (D-08):

**Layer 1 — the illegal state is hard to express.** ``SnapshotSpec`` is the only
way to name a snapshot and ``transactions_for`` is the only function in the
codebase that filters transactions by day for graph construction. Every edge
builder and every Cypher parameter set is fed from its output, so the classic
"four of five relationship types got the day filter" bug cannot be written.

**Layer 2 — provenance is measured, not declared.** ``end_day_exclusive`` is a
number a human wrote down; ``max_source_day`` is computed from the rows that
actually entered the graph. Checking the latter validates the computation, while
checking the former only validates the bookkeeping — and the bug that ships is
in the computation.

**Layer 3 — the guard runs in production, not only under pytest.** Tests run when
someone runs tests; the pipeline runs at 2am. ``attach_structural_features``
raises ``TrapBViolation`` unconditionally. Note it raises rather than asserting:
``python -O`` strips ``assert``, and a leak guard that can silently vanish is not
a guard.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import blake2b

import pandas as pd

from fds.schema import DAY, KEY, UID
from fds.splits import LAST_DAY

SNAPSHOT_ID = "snapshot_id"
END_DAY_EXCLUSIVE = "end_day_exclusive"
MAX_SOURCE_DAY = "max_source_day"
N_SOURCE_TXNS = "n_source_txns"
SOURCE_TXN_HASH = "source_txn_hash"
HAS_STRUCTURE = "has_structure"

PROVENANCE_COLUMNS = (
    SNAPSHOT_ID,
    END_DAY_EXCLUSIVE,
    MAX_SOURCE_DAY,
    N_SOURCE_TXNS,
    SOURCE_TXN_HASH,
)


class TrapBViolation(RuntimeError):
    """A structural feature was derived from data at or after its transaction."""


@dataclass(frozen=True)
class SnapshotSpec:
    """A point-in-time graph state.

    The graph for this snapshot contains transactions with ``day <
    end_day_exclusive``. The field name carries the boundary semantics so that
    ``<`` versus ``<=`` cannot be gotten wrong by reading the call site.
    """

    snapshot_id: str
    end_day_exclusive: int

    def __post_init__(self) -> None:
        if self.end_day_exclusive < 1:
            raise ValueError("end_day_exclusive must be at least 1 to contain any history")


def make_snapshot_id(end_day_exclusive: int) -> str:
    """Zero-padded so lexical order over snapshot ids equals temporal order."""
    return f"s{end_day_exclusive:04d}"


def snapshot_schedule(
    cadence_days: int, first_end_day: int, last_day: int = LAST_DAY
) -> list[SnapshotSpec]:
    """Build the expanding-window schedule.

    Ends at ``last_day`` rather than beyond it: a snapshot whose boundary exceeds
    the final transaction day can never be attached to anything.
    """
    if cadence_days < 1:
        raise ValueError("cadence_days must be at least 1")
    boundaries = range(first_end_day, last_day + 1, cadence_days)
    return [SnapshotSpec(make_snapshot_id(e), e) for e in boundaries]


def transactions_for(spec: SnapshotSpec, base: pd.DataFrame) -> pd.DataFrame:
    """The transactions visible to ``spec``'s graph — the single day filter.

    Nothing else in the codebase may filter by day for graph construction. If a
    second such filter appears, Layer 1 is gone.
    """
    if DAY not in base.columns:
        raise KeyError(f"{DAY!r} column is required to build a snapshot")
    return base.loc[base[DAY] < spec.end_day_exclusive]


def snapshot_provenance(
    source: pd.DataFrame, spec: SnapshotSpec, *, key_column: str = KEY
) -> dict[str, object]:
    """Measure what actually went into the graph.

    ``max_source_day`` is the load-bearing value: it is derived from the data, so
    a snapshot builder that leaked future rows reports a larger number here even
    though ``end_day_exclusive`` is unchanged.
    """
    if source.empty:
        raise ValueError(f"snapshot {spec.snapshot_id} has no source transactions")

    if key_column not in source.columns:
        raise KeyError(f"{key_column!r} is needed to fingerprint the snapshot's source rows")
    digest = blake2b(
        pd.util.hash_pandas_object(
            pd.Index(sorted(source[key_column])), index=False
        ).values.tobytes(),
        digest_size=8,
    ).hexdigest()

    observed_max = int(source[DAY].max())
    if observed_max >= spec.end_day_exclusive:
        raise TrapBViolation(
            f"snapshot {spec.snapshot_id} declares end_day_exclusive="
            f"{spec.end_day_exclusive} but its source transactions reach day "
            f"{observed_max}. The snapshot filter leaked."
        )

    return {
        SNAPSHOT_ID: spec.snapshot_id,
        END_DAY_EXCLUSIVE: spec.end_day_exclusive,
        MAX_SOURCE_DAY: observed_max,
        N_SOURCE_TXNS: len(source),
        SOURCE_TXN_HASH: digest,
    }


def attach_structural_features(
    txns: pd.DataFrame,
    snapshot_features: pd.DataFrame,
    *,
    feature_columns: list[str] | None = None,
) -> pd.DataFrame:
    """Join each transaction to the most recent snapshot that predates it.

    ``txns`` needs ``day`` and ``uid``. ``snapshot_features`` is one row per
    (uid, snapshot) carrying the provenance columns plus the structural features.

    On the merge direction — worth spelling out, because it is the one parameter
    the whole guarantee reduces to. Snapshot *E* contains transactions with
    ``day < E``, so its ``max_source_day <= E - 1``. A transaction at day *d*
    needs every contributing row strictly before *d*, which holds whenever
    ``E <= d``. So the valid snapshots are those with ``E <= d`` and we want the
    largest, which is ``direction="backward"`` with ``allow_exact_matches=True``.

    Using ``allow_exact_matches=False`` would also be safe but needlessly stale —
    it would reject ``E == d``, discarding up to a full cadence of legitimate
    history. The distinction only holds because ``end_day_exclusive`` is
    *exclusive*; had the boundary been inclusive, the opposite choice would be
    required. Either way the Layer 2 guard below is what actually enforces the
    rule, so a mistake here is caught rather than shipped.
    """
    for required in (DAY, UID):
        if required not in txns.columns:
            raise KeyError(f"transactions need a {required!r} column")
    if END_DAY_EXCLUSIVE not in snapshot_features.columns:
        raise KeyError(f"snapshot features need {END_DAY_EXCLUSIVE!r}")
    if MAX_SOURCE_DAY not in snapshot_features.columns:
        raise KeyError(
            f"snapshot features need {MAX_SOURCE_DAY!r} — the measured provenance "
            f"is what the Trap B guard checks, and it cannot be reconstructed later"
        )

    left = txns.sort_values(DAY, kind="stable")
    right = snapshot_features.sort_values(END_DAY_EXCLUSIVE, kind="stable")

    # merge_asof refuses keys of differing dtype, and `day` is int16 while a
    # boundary assembled from Python ints arrives as int64. Align on the left's
    # dtype rather than widening `day`, which is carried on every row.
    if right[END_DAY_EXCLUSIVE].dtype != left[DAY].dtype:
        right = right.astype({END_DAY_EXCLUSIVE: left[DAY].dtype})

    if feature_columns is not None:
        keep = [UID, END_DAY_EXCLUSIVE, *PROVENANCE_COLUMNS, *feature_columns]
        right = right[[c for c in dict.fromkeys(keep) if c in right.columns]]

    merged = pd.merge_asof(
        left,
        right,
        left_on=DAY,
        right_on=END_DAY_EXCLUSIVE,
        by=UID,
        direction="backward",
        allow_exact_matches=True,
    )

    merged[HAS_STRUCTURE] = merged[MAX_SOURCE_DAY].notna()
    assert_trap_b(merged)
    return merged


def assert_trap_b(attached: pd.DataFrame) -> None:
    """Raise unless every attached feature predates its transaction.

    Checks the *measured* ``max_source_day``, not the declared boundary. Rows with
    no snapshot yet are left as NaN and skipped — deliberately not filled with 0,
    since 0 is a real degree value and conflating "no structure yet" with
    "isolated node" teaches the model a signal that does not exist (D-20).
    """
    if MAX_SOURCE_DAY not in attached.columns:
        raise TrapBViolation(
            f"{MAX_SOURCE_DAY!r} is absent, so the temporal guarantee cannot be "
            f"checked. Do not proceed on the assumption that it holds."
        )

    have = attached[MAX_SOURCE_DAY].notna()
    if not have.any():
        return

    violating = have & (attached[MAX_SOURCE_DAY].astype("Float64") >= attached[DAY])
    n_bad = int(violating.sum())
    if n_bad:
        sample = attached.loc[violating, [DAY, MAX_SOURCE_DAY, SNAPSHOT_ID]].head(5)
        raise TrapBViolation(
            f"{n_bad} transactions carry structural features derived from data at "
            f"or after their own timestamp. First offenders:\n{sample.to_string()}"
        )
