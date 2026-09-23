"""Client reconstruction: stability, normalisation and null policy."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fds.entities import (
    UID_RECIPES,
    NullPolicy,
    UidRecipe,
    add_d1n,
    build_uid,
    client_size_diagnostics,
)
from fds.schema import D1N, DAY


@pytest.fixture
def frame() -> pd.DataFrame:
    return add_d1n(
        pd.DataFrame(
            {
                "TransactionID": [1, 2, 3, 4, 5],
                DAY: pd.Series([10, 20, 10, 30, 10], dtype="int16"),
                "D1": [10.0, 20.0, 10.0, 30.0, np.nan],
                "card1": [1001, 1001, 2002, 1001, 1001],
                "card2": [500.0, 500.0, 321.0, 500.0, 500.0],
                "addr1": [325.0, 325.0, 204.0, np.nan, 325.0],
                "P_emaildomain": ["Gmail.com ", "gmail.com", "aol.com", "gmail.com", "gmail.com"],
            }
        )
    )


def test_d1n_is_constant_for_a_card_across_time(frame):
    # Rows 1, 2 and 4 share card1 and were registered on the same day, so their
    # inferred origin must agree despite transacting on days 10, 20 and 30.
    assert frame.loc[[0, 1, 3], D1N].tolist() == [0, 0, 0]


def test_d1n_stays_nullable_rather_than_filled(frame):
    assert pd.isna(frame.loc[4, D1N]), "a missing D1 is an absent anchor, not a zero one"


def test_uid_is_stable_across_processes():
    """The property plan.md's hash() loses once a string enters the key."""
    import subprocess
    import sys

    snippet = (
        "import pandas as pd, numpy as np;"
        "from fds.entities import build_uid, UID_RECIPES, add_d1n;"
        "df = add_d1n(pd.DataFrame({'day': pd.Series([10], dtype='int16'), 'D1':[10.0],"
        "'card1':[1001], 'card2':[500.0], 'addr1':[325.0], 'P_emaildomain':['gmail.com']}));"
        "print(build_uid(df, UID_RECIPES['v3_plus_email']).iloc[0])"
    )
    runs = {
        subprocess.run(
            [sys.executable, "-c", snippet],
            capture_output=True,
            text=True,
            check=True,
            env={"PYTHONHASHSEED": "random", "PATH": "/usr/bin:/bin"},
        ).stdout.strip()
        for _ in range(2)
    }
    assert len(runs) == 1, "uid changed between processes"


def test_email_normalisation_groups_case_and_whitespace_variants(frame):
    uid = build_uid(frame, UID_RECIPES["v3_plus_email"])
    # Rows 1 and 2 differ only by "Gmail.com " vs "gmail.com".
    assert uid.iloc[0] == uid.iloc[1]


def test_stricter_recipe_actually_splits_a_client_the_looser_one_merges():
    """Behavioural, not tautological.

    `strict >= loose` follows from the key construction and cannot fail for any
    fixture. What is worth testing is that the extra component does real work:
    two rows identical on card/addr/D1n but differing in email must be one
    client under v1 and two under v3.
    """
    df = add_d1n(
        pd.DataFrame(
            {
                DAY: pd.Series([10, 10], dtype="int16"),
                "D1": [10.0, 10.0],
                "card1": [1001, 1001],
                "card2": [500.0, 500.0],
                "addr1": [325.0, 325.0],
                "P_emaildomain": ["gmail.com", "yahoo.com"],
            }
        )
    )
    assert build_uid(df, UID_RECIPES["v1_card1_addr1_d1n"]).nunique() == 1
    assert build_uid(df, UID_RECIPES["v3_plus_email"]).nunique() == 2


def test_null_policies_differ_only_where_components_are_missing():
    df = add_d1n(
        pd.DataFrame(
            {
                DAY: pd.Series([10, 20, 10], dtype="int16"),
                "D1": [10.0, 20.0, 10.0],
                "card1": [1001, 1001, 1001],
                "addr1": [np.nan, np.nan, 325.0],
            }
        )
    )
    base = UID_RECIPES["v1_card1_addr1_d1n"]
    singleton = UidRecipe(base.name, base.columns, base.description, NullPolicy.SINGLETON)

    assert build_uid(df, base).nunique() == 2, "sentinel groups the two null-addr rows"
    assert build_uid(df, singleton).nunique() == 3, "singleton splits them"


def test_diagnostics_expose_an_oversized_client():
    uid = pd.Series(["mega"] * 90 + [f"c{i}" for i in range(10)])
    stats = client_size_diagnostics(uid)
    assert stats["max_client_share"] == pytest.approx(0.9)
    assert stats["n_clients"] == 11
