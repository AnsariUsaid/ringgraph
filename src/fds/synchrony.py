"""Do linked clients transact *together*, or merely share an unusual attribute?

This is the gate that decides what the project is about (D-38). Client-level
homophily cannot separate "these clients are coordinated" from "this device
string is rare and rare device strings are fraudulent" — and the second is just
an ordinary categorical feature that a tabular model already exploits. Temporal
structure is what distinguishes them: a rare-attribute effect has none,
coordination does.

**The null is the whole design.** Comparing against a homogeneous Poisson process
would be wrong and would almost certainly "confirm" coordination that is not
there, because individual customers are bursty all by themselves — someone buys
four things in an hour. A Poisson baseline would read that ordinary personal
burstiness as a ring.

So the null preserves each client's own timing pattern exactly and destroys only
the *alignment between* clients: every client's transaction sequence is shifted
by a random offset, circularly, within the observation window. Intra-client
burstiness survives untouched; inter-client synchrony does not. The statistic is
then the number of transaction pairs from *different* clients in the same
component falling within Δt of each other.

This is the shift-null used for spike trains in neuroscience, and it is the right
one here for the same reason: the question is coincidence between sources, not
the rate of any one source.
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np
import pandas as pd


def _pairs_within(sorted_times: np.ndarray, delta: float) -> int:
    """Count ordered pairs (i < j) with ``t_j - t_i <= delta``."""
    if sorted_times.size < 2:
        return 0
    right = np.searchsorted(sorted_times, sorted_times + delta, side="right")
    return int((right - np.arange(sorted_times.size) - 1).sum())


def coincidence_count(times: np.ndarray, uid_codes: np.ndarray, delta: float) -> int:
    """Pairs of transactions from *different* clients falling within ``delta``.

    Computed as (all pairs within delta) − (same-client pairs within delta), so a
    single client's own rapid-fire purchases never count as synchrony.
    """
    order = np.argsort(times, kind="stable")
    t, u = times[order], uid_codes[order]
    total = _pairs_within(t, delta)

    same = 0
    for code in np.unique(u):
        same += _pairs_within(np.sort(t[u == code]), delta)
    return total - same


def shift_null(
    times: np.ndarray,
    uid_codes: np.ndarray,
    delta: float,
    span: float,
    rng: np.random.Generator,
) -> int:
    """One draw: shift each client's whole sequence circularly, then recount."""
    shifted = times.copy()
    for code in np.unique(uid_codes):
        mask = uid_codes == code
        shifted[mask] = np.mod(times[mask] + rng.uniform(0.0, span), span)
    return coincidence_count(shifted, uid_codes, delta)


def synchrony_test(
    groups: list[tuple[np.ndarray, np.ndarray]],
    *,
    delta: float,
    span: float,
    rng: np.random.Generator,
    n_permutations: int = 50,
) -> dict[str, float | int]:
    """Aggregate observed coincidences against the shift null across components.

    Aggregating before comparing — rather than testing each component alone — is
    what gives the test power. Individual components hold a handful of
    transactions each; the question is whether the population of linked clients
    shows alignment, and that is a sum.
    """
    if not groups:
        return {"n_groups": 0}

    observed = sum(coincidence_count(t, u, delta) for t, u in groups)

    draws = np.empty(n_permutations, dtype=float)
    for i in range(n_permutations):
        draws[i] = sum(shift_null(t, u, delta, span, rng) for t, u in groups)

    null_mean = float(draws.mean())
    null_sd = float(draws.std(ddof=1)) if draws.size > 1 else 0.0
    return {
        "n_groups": len(groups),
        "n_transactions": int(sum(t.size for t, _ in groups)),
        "observed": int(observed),
        "null_mean": null_mean,
        "null_sd": null_sd,
        "ratio": float(observed / null_mean) if null_mean else float("nan"),
        "z": float((observed - null_mean) / null_sd) if null_sd else float("nan"),
    }


def build_groups(
    df: pd.DataFrame,
    members: pd.DataFrame,
    *,
    uid_column: str,
    time_column: str,
    components: list[int] | None = None,
    min_clients: int = 3,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Collect (times, client codes) per component, ready for ``synchrony_test``."""
    joined = df.merge(members, left_on=uid_column, right_on="uid", how="inner")
    if components is not None:
        joined = joined[joined["component"].isin(components)]

    groups: list[tuple[np.ndarray, np.ndarray]] = []
    for _, block in joined.groupby("component", observed=True):
        codes = pd.factorize(block[uid_column])[0]
        if np.unique(codes).size < min_clients:
            continue
        groups.append((block[time_column].to_numpy(dtype=float), codes))
    return groups


def per_component_synchrony(
    df: pd.DataFrame,
    members: pd.DataFrame,
    *,
    uid_column: str,
    time_column: str,
    delta: float,
    span: float,
    rng: np.random.Generator,
    n_permutations: int = 60,
    min_clients: int = 3,
) -> pd.DataFrame:
    """Observed and null coincidences for every component separately.

    Needed because the aggregate comparison is confounded by size: null
    coincidences scale roughly with the square of a component's transaction
    count, so a dense component has a far larger null and therefore a smaller
    ratio even when its absolute excess is bigger. Comparing a fraud-bearing set
    that averages 168 transactions per component against a fraud-free set
    averaging 18 is a Simpson's paradox waiting to happen — and in this data it
    reverses the apparent direction.
    """
    joined = df.merge(members, left_on=uid_column, right_on="uid", how="inner")
    rows = []
    for component, block in joined.groupby("component", observed=True):
        codes = pd.factorize(block[uid_column])[0]
        n_clients = int(np.unique(codes).size)
        if n_clients < min_clients:
            continue
        times = block[time_column].to_numpy(dtype=float)
        observed = coincidence_count(times, codes, delta)
        null = float(
            np.mean([shift_null(times, codes, delta, span, rng) for _ in range(n_permutations)])
        )
        rows.append(
            {
                "component": component,
                "n_transactions": int(times.size),
                "n_clients": n_clients,
                "observed": observed,
                "null_mean": null,
            }
        )
    return pd.DataFrame(rows)


DEFAULT_SIZE_BINS = (0, 20, 50, 150, 10**9)


def stratified_comparison(
    per_component: pd.DataFrame,
    summary: pd.DataFrame,
    *,
    bins: tuple[int, ...] = DEFAULT_SIZE_BINS,
) -> pd.DataFrame:
    """Compare fraud-bearing and fraud-free components within size strata.

    ``kind`` is 'candidate' for components holding two or more fraud clients and
    'control' for those holding none. Components with exactly one fraud client
    are excluded: they are neither a candidate ring nor a clean control.
    """
    merged = per_component.merge(summary[["component", "n_fraud_clients"]], on="component")
    merged["kind"] = np.select(
        [merged["n_fraud_clients"] >= 2, merged["n_fraud_clients"] == 0],
        ["candidate", "control"],
        default="single",
    )
    merged = merged[merged["kind"] != "single"]
    labels = [f"{lo + 1}-{hi}" for lo, hi in pairwise(bins)]
    labels[-1] = f">{bins[-2]}"
    merged["size_bin"] = pd.cut(merged["n_transactions"], list(bins), labels=labels)

    grouped = merged.groupby(["size_bin", "kind"], observed=True)
    out = grouped.agg(
        n_components=("component", "size"),
        observed=("observed", "sum"),
        null_mean=("null_mean", "sum"),
    ).reset_index()
    out["ratio"] = out["observed"] / out["null_mean"].replace(0, np.nan)
    return out
