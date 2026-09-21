"""Client reconstruction.

The dataset has no account id, so client identity is inferred (plan.md §Part 2).
The established approach recovers a stable per-card origin from ``D1`` — days
since the card began — which is constant per card:

    D1n = day - D1          approximate card registration day
    uid = digest(card1, addr1, D1n)

Two corrections to the plan's pseudocode:

1. It writes ``hash(...)``. Python salts ``hash()`` of *strings* per process via
   ``PYTHONHASHSEED``. Tuples of ints are unaffected, so the plan's literal
   ``hash(card1, addr1, D1n)`` would in fact be stable — but the plan also asks
   for stricter variants "adding card2 / P_emaildomain", and the moment an email
   domain enters the key the uid changes on every run and nothing reproduces
   (D-06). Rather than have reproducibility depend on which recipe is selected,
   this module uses blake2b over a normalised joined string throughout.

2. Null handling is unspecified, and it matters more than it looks. ``addr1`` is
   missing for roughly a tenth of rows and ``D1`` for a small fraction. Two
   policies are available and neither is obviously right, so the choice is
   explicit and measured rather than implied:

   - ``SENTINEL`` (default): nulls become a literal token, so rows agreeing on
     their present components group together. Risk: manufactures one oversized
     client if a component is mostly null.
   - ``SINGLETON``: any null makes the row its own client. Safe against fake
     mega-clients, but discards real structure.

   ``client_size_diagnostics`` exists so the choice is defended with a number.
   A recipe that produces a client of implausible size has failed, and that must
   surface at profiling time rather than as a suspiciously dense community later.

Recipes live here as a registry keyed by name; config carries only the name
(D-15). A recipe embeds real decisions — normalisation, null policy — and those
are code, not data.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import blake2b

import numpy as np
import pandas as pd

from fds.schema import D1N, DAY

# Unit separator: cannot occur in any field value, so the join is unambiguous and
# ("1", "23") cannot collide with ("12", "3").
_SEP = "\x1f"
_NULL_TOKEN = "\x00NA"
_DIGEST_BYTES = 8  # 64-bit; collision risk across ~10^5 clients is negligible


class NullPolicy(StrEnum):
    SENTINEL = "sentinel"
    SINGLETON = "singleton"


@dataclass(frozen=True)
class UidRecipe:
    """A client-identity definition. Frozen so a recipe cannot be edited in place."""

    name: str
    columns: tuple[str, ...]
    description: str
    null_policy: NullPolicy = NullPolicy.SENTINEL


# plan.md asks for at least two variants at different strictness, and for the
# sensitivity of downstream structure to the choice to be reported. Strictness
# increases down the list: more components means finer, more numerous clients.
UID_RECIPES: dict[str, UidRecipe] = {
    "v1_card1_addr1_d1n": UidRecipe(
        name="v1_card1_addr1_d1n",
        columns=("card1", "addr1", D1N),
        description="Plan baseline: card, billing address and inferred card-origin day.",
    ),
    "v2_plus_card2": UidRecipe(
        name="v2_plus_card2",
        columns=("card1", "card2", "addr1", D1N),
        description="Adds card2, splitting clients that share card1 but differ in issuer range.",
    ),
    "v3_plus_email": UidRecipe(
        name="v3_plus_email",
        columns=("card1", "card2", "addr1", D1N, "P_emaildomain"),
        description="Strictest: also requires the purchaser email domain to match.",
    ),
}

DEFAULT_RECIPE = "v1_card1_addr1_d1n"


def add_d1n(df: pd.DataFrame) -> pd.DataFrame:
    """Attach ``D1n``, the approximate card registration day.

    ``D1`` is days since the card began, so ``day - D1`` is constant for a card
    across its transactions. Kept nullable (``Int16``) rather than filled: a
    missing ``D1`` is an absent anchor, not a zero-valued one.

    This is a per-row arithmetic identity with no aggregation, so it carries no
    temporal leak — worth stating because a recipe built on an aggregate (say,
    "most common email per card") would leak across the split boundary.
    """
    return assign_d1n(df.copy())


def assign_d1n(df: pd.DataFrame) -> pd.DataFrame:
    """In-place variant for callers that already hold a private copy.

    ``add_derived`` copies a 436-column frame once; without this it would copy it
    twice, roughly doubling both the wall time and the peak memory of ingest.
    """
    df[D1N] = (df[DAY] - df["D1"]).astype("Int16")
    return df


def _normalise(series: pd.Series, column: str) -> pd.Series:
    """Render one component as a canonical string, independent of storage dtype.

    Without this, ``addr1`` read as float yields "325.0" in one run and "325" in
    another depending on whether nulls were present, silently changing uids.
    """
    if column in {"P_emaildomain", "R_emaildomain"}:
        norm = series.astype("string").str.strip().str.lower()
    elif pd.api.types.is_float_dtype(series) or pd.api.types.is_integer_dtype(series):
        norm = series.astype("Float64").round().astype("Int64").astype("string")
    else:
        norm = series.astype("string").str.strip()
    return norm


def _digest(joined: str) -> str:
    return blake2b(joined.encode("utf-8"), digest_size=_DIGEST_BYTES).hexdigest()


def build_uid(df: pd.DataFrame, recipe: UidRecipe) -> pd.Series:
    """Compute the stable client key for every row under ``recipe``.

    Returns a string Series of blake2b digests, reproducible across processes and
    machines. Under ``SINGLETON``, rows with any missing component receive a key
    unique to that row, derived from the TransactionID so it is still stable.
    """
    missing = [c for c in recipe.columns if c not in df.columns]
    if missing:
        raise KeyError(f"recipe {recipe.name!r} needs columns {missing}, which are absent")

    parts = [_normalise(df[c], c) for c in recipe.columns]
    any_null = np.zeros(len(df), dtype=bool)
    for p in parts:
        any_null |= p.isna().to_numpy()

    filled = [p.fillna(_NULL_TOKEN) for p in parts]
    joined = filled[0].str.cat(filled[1:], sep=_SEP)

    uid = joined.map(_digest)

    if recipe.null_policy is NullPolicy.SINGLETON and any_null.any():
        # Prefix distinguishes the namespace, so a singleton can never collide
        # with a genuine group key.
        singleton_src = "singleton" + _SEP + df.index.astype("string")
        uid = uid.mask(any_null, singleton_src.map(_digest))

    return uid.astype("string").rename("uid")


def uid_code(uid: pd.Series) -> pd.Series:
    """Compact within-run integer code for a uid, for joins and graph node ids.

    Not stable across runs by design — the digest is the stable key. Use this only
    where a run-local dense integer is needed.
    """
    codes, _ = pd.factorize(uid, sort=True)
    return pd.Series(codes, index=uid.index, dtype="int32", name="uid_code")


def client_size_diagnostics(uid: pd.Series) -> dict[str, float | int]:
    """Numbers that decide whether a recipe produced plausible clients.

    ``max_client_share`` is the one to watch: a single client holding a large
    share of all transactions means the null policy manufactured a mega-client
    rather than reconstructing anyone.
    """
    sizes = uid.value_counts()
    n = int(sizes.sum())
    return {
        "n_transactions": n,
        "n_clients": int(sizes.size),
        "mean_client_size": float(sizes.mean()),
        "median_client_size": float(sizes.median()),
        "p99_client_size": float(sizes.quantile(0.99)),
        "max_client_size": int(sizes.iloc[0]),
        "max_client_share": float(sizes.iloc[0] / n),
        "singleton_client_share": float((sizes == 1).sum() / sizes.size),
    }
