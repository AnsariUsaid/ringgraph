"""Structural features end-to-end: the real pipeline must respect Trap B.

tests/test_trap_b.py exercises the attachment machinery with a miniature feature
function. This exercises the *production* path — build_links, networkx, snapshot
provenance — so a leak introduced in the real feature code is caught too.
"""

from __future__ import annotations

import pandas as pd
import pytest

from fds.links import LinkParams
from fds.schema import DAY, KEY, UID
from fds.snapshots import MAX_SOURCE_DAY, SnapshotSpec, attach_structural_features
from fds.structural import snapshot_feature_table, structural_features

LINKS = ("DeviceInfo",)
PARAMS = LinkParams(min_degree=2, max_degree=50, min_weight=1)


@pytest.fixture
def base() -> pd.DataFrame:
    """Clients A and B only start sharing a device on day 80.

    Before day 80 they are unconnected, so a correct pipeline reports degree 0
    for any transaction earlier than that. A leak reports 1.
    """
    # isFraud is present on purpose: the pipeline must drop it, and a fixture
    # without it made the "no label reaches the features" test unfalsifiable.
    rows = [
        (1, "A", 10, "laptop-a", 1),
        (2, "B", 20, "laptop-b", 0),
        (3, "A", 70, "laptop-a", 1),
        (4, "A", 80, "shared-box", 1),
        (5, "B", 85, "shared-box", 0),
        (6, "A", 150, "shared-box", 1),
        (7, "B", 150, "shared-box", 0),
        (8, "C", 30, "laptop-c", 0),
    ]
    return pd.DataFrame(rows, columns=[KEY, UID, DAY, "DeviceInfo", "isFraud"]).astype(
        {DAY: "int16"}
    )


def _specs() -> list[SnapshotSpec]:
    return [SnapshotSpec("s0060", 60), SnapshotSpec("s0100", 100), SnapshotSpec("s0160", 160)]


class TestStructuralFeatures:
    def test_isolated_client_gets_a_genuine_zero(self, base):
        """Degree 0 is a true statement about an isolated node, not missing data."""
        early = base[base[DAY] < 60]
        features = structural_features(early, link_columns=LINKS, params=PARAMS)
        assert set(features[UID]) == {"A", "B", "C"}
        assert (features["st_degree"] == 0).all()
        assert (features["st_component_size"] == 1).all()

    def test_link_appears_only_once_the_sharing_has_happened(self, base):
        later = base[base[DAY] < 100]
        features = structural_features(later, link_columns=LINKS, params=PARAMS).set_index(UID)
        assert features.loc["A", "st_degree"] == 1
        assert features.loc["B", "st_degree"] == 1
        assert features.loc["C", "st_degree"] == 0
        assert features.loc["A", "st_component_size"] == 2


class TestTrapBThroughTheRealPipeline:
    def test_transaction_before_the_link_does_not_see_it(self, base):
        table = snapshot_feature_table(
            base, _specs(), link_columns=LINKS, params=PARAMS, progress=False
        )
        attached = attach_structural_features(base, table)

        # Day 70: newest usable snapshot is s0060, which predates the day-80
        # sharing entirely. Degree must be 0, not 1.
        row = attached[(attached[UID] == "A") & (attached[DAY] == 70)].iloc[0]
        assert row["st_degree"] == 0, "structural feature leaked a future link"
        assert row[MAX_SOURCE_DAY] < 70

        # Day 150: s0100 has seen the day-80/85 sharing, so the link is visible.
        later = attached[(attached[UID] == "A") & (attached[DAY] == 150)].iloc[0]
        assert later["st_degree"] == 1
        assert later[MAX_SOURCE_DAY] < 150

    def test_features_carry_measured_provenance(self, base):
        table = snapshot_feature_table(
            base, _specs(), link_columns=LINKS, params=PARAMS, progress=False
        )
        for snapshot_id, block in table.groupby("snapshot_id"):
            declared = int(block["end_day_exclusive"].iloc[0])
            assert int(block[MAX_SOURCE_DAY].iloc[0]) < declared, snapshot_id

    def test_no_label_column_can_reach_the_feature_table(self, base):
        table = snapshot_feature_table(
            base, _specs(), link_columns=LINKS, params=PARAMS, progress=False
        )
        assert "isFraud" in base.columns, "fixture must carry a label to be dropped"
        assert "isFraud" not in table.columns
        assert not any("fraud" in c.lower() for c in table.columns)
