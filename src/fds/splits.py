"""Temporal splits — fixed constants, deliberately not configurable.

plan.md §Part 2 fixes the boundaries: train days 0–119, validation 120–150,
test 151–181. These live in code rather than YAML (D-13). As a config value
somebody eventually nudges a boundary because a number looks better and the diff
is one innocuous line; as a constant they cannot move without a visible code
change. The split is never legitimately swept, so the rigidity costs nothing.

There is no cached split-assignment artefact, for the same reason: a file on disk
can contradict this module, and then two places claim to define the truth.
"""

from __future__ import annotations

from enum import StrEnum
from itertools import pairwise

import pandas as pd

SECONDS_PER_DAY = 86_400

# ``TransactionDT`` is documented as starting at 86,400 rather than 0, so the raw
# floor division yields days 1..182 while plan.md's split boundaries are stated over
# days 0..181 (D-22). Shifting by this origin reconciles the two; without it the
# final day falls outside every split and the train window silently loses a day.
# ``verify_day_range`` asserts the shift was correct against the real data rather
# than trusting this constant.
DAY_ORIGIN_RAW = 1

TRAIN_START_DAY = 0
TRAIN_END_DAY = 119  # inclusive
VAL_START_DAY = 120
VAL_END_DAY = 150  # inclusive
TEST_START_DAY = 151
TEST_END_DAY = 181  # inclusive

FIRST_DAY = TRAIN_START_DAY
LAST_DAY = TEST_END_DAY


class Split(StrEnum):
    TRAIN = "train"
    VAL = "val"
    TEST = "test"


SPLIT_BOUNDS: dict[Split, tuple[int, int]] = {
    Split.TRAIN: (TRAIN_START_DAY, TRAIN_END_DAY),
    Split.VAL: (VAL_START_DAY, VAL_END_DAY),
    Split.TEST: (TEST_START_DAY, TEST_END_DAY),
}


def day_from_transaction_dt(transaction_dt: pd.Series) -> pd.Series:
    """``TransactionDT`` is a seconds offset from an unknown reference (plan.md §Part 2).

    Its absolute value is meaningless; only the ordering matters, which is all a
    temporal split needs. The result is shifted to a 0-based day index so it lines
    up with the split boundaries above — see ``DAY_ORIGIN_RAW``.
    """
    return (transaction_dt // SECONDS_PER_DAY - DAY_ORIGIN_RAW).astype("int16")


def verify_day_range(day: pd.Series) -> None:
    """Fail loudly if the derived day index does not span exactly 0..LAST_DAY.

    Called by the ingest script. The day origin is an assumption about the raw
    data; this is where that assumption gets checked against reality instead of
    propagating quietly into every split downstream.
    """
    observed_min, observed_max = int(day.min()), int(day.max())
    if (observed_min, observed_max) != (FIRST_DAY, LAST_DAY):
        raise ValueError(
            f"derived day index spans {observed_min}..{observed_max}, expected "
            f"{FIRST_DAY}..{LAST_DAY}. TransactionDT's origin differs from the "
            f"assumed DAY_ORIGIN_RAW={DAY_ORIGIN_RAW}; fix the constant rather "
            f"than widening the split boundaries."
        )


def assign_split(day: pd.Series) -> pd.Series:
    """Map a day column to train/val/test.

    Days outside the known range become NA rather than being silently folded into
    an adjacent split — an out-of-range day means an upstream assumption broke and
    should surface, not be absorbed.
    """
    out = pd.Series(pd.NA, index=day.index, dtype="object")
    for split, (lo, hi) in SPLIT_BOUNDS.items():
        out = out.mask(day.between(lo, hi), str(split))
    return out.astype(pd.CategoricalDtype(categories=[str(s) for s in Split]))


def _validate_bounds() -> None:
    """The three windows must be contiguous, ordered and gapless."""
    ordered = [SPLIT_BOUNDS[s] for s in (Split.TRAIN, Split.VAL, Split.TEST)]
    for (_, prev_hi), (next_lo, _) in pairwise(ordered):
        if next_lo != prev_hi + 1:
            raise ValueError(f"split windows are not contiguous at {prev_hi}->{next_lo}")
    for lo, hi in ordered:
        if lo > hi:
            raise ValueError(f"inverted split window: {lo}..{hi}")


_validate_bounds()
