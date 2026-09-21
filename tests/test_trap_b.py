"""Trap B: structural features may only come from data strictly before their transaction.

plan.md's Verification section requires this be "a test, not a convention". The
tests that matter here are the *value* tests. A predicate test — assert
``max_source_day < day`` — can pass vacuously: if every feature comes back NaN,
the condition is trivially satisfiable and the suite stays green while the
pipeline produces nothing. A test that asserts a specific number cannot.
"""

from __future__ import annotations

import pandas as pd
import pytest

from fds.schema import DAY, KEY, UID
from fds.snapshots import (
    END_DAY_EXCLUSIVE,
    HAS_STRUCTURE,
    MAX_SOURCE_DAY,
    SnapshotSpec,
    TrapBViolation,
    assert_trap_b,
    attach_structural_features,
    snapshot_provenance,
    snapshot_schedule,
    transactions_for,
)

# uid "A" transacts twice before day 60 and five more times after, so its degree
# is 2 under a past-only computation at day 60 and 7 under an all-data one. The
# two answers differ, which is the entire point of the fixture: a leak changes a
# number rather than merely a label.
_A_EARLY_DAYS = [10, 20]
_A_LATE_DAYS = [60, 65, 70, 75, 80]


@pytest.fixture
def txns() -> pd.DataFrame:
    rows = []
    tid = 1
    for day in _A_EARLY_DAYS + _A_LATE_DAYS:
        rows.append((tid, "A", day))
        tid += 1
    for day in (5, 30, 95):
        rows.append((tid, "B", day))
        tid += 1
    for day in (70, 100):
        rows.append((tid, "C", day))
        tid += 1
    return pd.DataFrame(rows, columns=[KEY, UID, DAY]).astype({DAY: "int16"})


def _degree_features(base: pd.DataFrame, specs: list[SnapshotSpec]) -> pd.DataFrame:
    """A miniature of the real feature pipeline: per-client transaction degree.

    Deliberately routed through ``transactions_for`` and ``snapshot_provenance``
    rather than reimplementing the filter, so the test exercises the production
    path. If someone loosens the filter in ``transactions_for``, this breaks.
    """
    frames = []
    for spec in specs:
        source = transactions_for(spec, base)
        if source.empty:
            continue
        prov = snapshot_provenance(source, spec)
        degree = source.groupby(UID, observed=True).size().rename("degree").reset_index()
        for key, value in prov.items():
            degree[key] = value
        frames.append(degree)
    return pd.concat(frames, ignore_index=True)


class TestSnapshotFiltering:
    def test_transactions_for_excludes_the_boundary_day(self, txns):
        source = transactions_for(SnapshotSpec("s0060", 60), txns)
        assert source[DAY].max() == 30
        assert 60 not in set(source[DAY])

    def test_schedule_never_exceeds_the_final_day(self):
        specs = snapshot_schedule(cadence_days=14, first_end_day=28, last_day=181)
        assert all(s.end_day_exclusive <= 181 for s in specs)
        assert [s.end_day_exclusive for s in specs] == sorted({s.end_day_exclusive for s in specs})

    def test_provenance_measures_rather_than_trusts(self, txns):
        spec = SnapshotSpec("s0060", 60)
        prov = snapshot_provenance(transactions_for(spec, txns), spec)
        assert prov[MAX_SOURCE_DAY] == 30
        assert prov[MAX_SOURCE_DAY] < spec.end_day_exclusive

    def test_provenance_rejects_a_leaked_source_set(self, txns):
        """A snapshot fed rows past its own boundary must refuse to describe itself."""
        spec = SnapshotSpec("s0060", 60)
        leaked = txns  # unfiltered: reaches day 100
        with pytest.raises(TrapBViolation, match="leaked"):
            snapshot_provenance(leaked, spec)


class TestAttachedValues:
    """The mutation tests. These assert numbers, not predicates."""

    def test_feature_reflects_only_prior_history(self, txns):
        specs = [SnapshotSpec("s0060", 60), SnapshotSpec("s0120", 120)]
        attached = attach_structural_features(txns, _degree_features(txns, specs))

        row = attached[(attached[UID] == "A") & (attached[DAY] == 70)].iloc[0]
        # 2, not 7: at day 70 the newest usable snapshot is s0060, which saw only
        # A's two transactions on days 10 and 20.
        assert row["degree"] == 2, "structural feature leaked future transactions"
        assert row[MAX_SOURCE_DAY] == 30
        assert row[END_DAY_EXCLUSIVE] == 60

    def test_exclusive_boundary_snapshot_is_usable(self, txns):
        """A snapshot ending exactly at day d is legal for a transaction on day d.

        Snapshot E contains ``day < E``, so E == d still means every contributing
        row is strictly before d. Rejecting it would discard up to a full cadence
        of legitimate history for no safety gain.
        """
        specs = [SnapshotSpec("s0060", 60)]
        attached = attach_structural_features(txns, _degree_features(txns, specs))
        row = attached[(attached[UID] == "A") & (attached[DAY] == 60)].iloc[0]
        assert row[HAS_STRUCTURE]
        assert row["degree"] == 2

    def test_rows_before_the_first_snapshot_are_nan_not_zero(self, txns):
        specs = [SnapshotSpec("s0060", 60)]
        attached = attach_structural_features(txns, _degree_features(txns, specs))
        early = attached[(attached[UID] == "A") & (attached[DAY] == 10)].iloc[0]
        assert pd.isna(early["degree"]), "absent structure must not be filled with 0"
        assert not early[HAS_STRUCTURE]

    def test_later_snapshot_supersedes_earlier(self, txns):
        specs = [SnapshotSpec("s0060", 60), SnapshotSpec("s0090", 90)]
        attached = attach_structural_features(txns, _degree_features(txns, specs))
        b95 = attached[(attached[UID] == "B") & (attached[DAY] == 95)].iloc[0]
        assert b95[END_DAY_EXCLUSIVE] == 90
        assert b95["degree"] == 2  # B transacted on days 5 and 30 before day 90


class TestGuardLiveness:
    """A guard that has rotted into a no-op must itself fail a test."""

    def test_guard_raises_on_a_corrupted_attachment(self, txns):
        specs = [SnapshotSpec("s0060", 60)]
        attached = attach_structural_features(txns, _degree_features(txns, specs))
        corrupted = attached.copy()
        corrupted.loc[corrupted[HAS_STRUCTURE], MAX_SOURCE_DAY] = 999
        with pytest.raises(TrapBViolation, match="at or after"):
            assert_trap_b(corrupted)

    def test_guard_raises_when_provenance_is_missing(self, txns):
        with pytest.raises(TrapBViolation, match="cannot be checked"):
            assert_trap_b(txns)

    def test_attach_refuses_features_without_measured_provenance(self, txns):
        bare = pd.DataFrame({UID: ["A"], END_DAY_EXCLUSIVE: [60], "degree": [2]})
        with pytest.raises(KeyError, match=MAX_SOURCE_DAY):
            attach_structural_features(txns, bare)
