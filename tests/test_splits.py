"""Temporal splits and the day derivation."""

from __future__ import annotations

import pandas as pd
import pytest

from fds import splits


def test_windows_cover_every_day_exactly_once():
    days = pd.Series(range(splits.FIRST_DAY, splits.LAST_DAY + 1), dtype="int16")
    assigned = splits.assign_split(days)
    assert assigned.notna().all(), "a day fell outside every split"
    assert assigned.value_counts().to_dict() == {"train": 120, "val": 31, "test": 31}


def test_splits_are_ordered_in_time():
    days = pd.Series(range(splits.FIRST_DAY, splits.LAST_DAY + 1), dtype="int16")
    frame = pd.DataFrame({"day": days, "split": splits.assign_split(days)})
    maxima = frame.groupby("split", observed=True)["day"].max()
    assert maxima["train"] < frame[frame.split == "val"]["day"].min()
    assert maxima["val"] < frame[frame.split == "test"]["day"].min()


def test_day_derivation_is_zero_based():
    """TransactionDT starts at 86400, so the raw floor division is 1-based."""
    assert splits.day_from_transaction_dt(pd.Series([86_400])).iloc[0] == 0


def test_verify_day_range_rejects_an_unshifted_index():
    unshifted = pd.Series(range(1, 183), dtype="int16")
    with pytest.raises(ValueError, match="DAY_ORIGIN_RAW"):
        splits.verify_day_range(unshifted)


def test_out_of_range_days_are_not_absorbed_into_a_split():
    assert pd.isna(splits.assign_split(pd.Series([999], dtype="int16")).iloc[0])
