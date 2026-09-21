"""Data profiling and the Trap A label-homogeneity measurement.

plan.md's week-one gate: reconstruct client identity, then measure the share of
clients that are all-fraud or all-legitimate. If clients are near-pure, fraud is
clustered on client identity by construction and any "discovery" that fraud
concentrates in dense clusters has rediscovered the labelling rule.

Two refinements the raw measurement needs before it means anything:

1. **Singleton clients are trivially pure.** A client with one transaction is
   100% homogeneous by definition, and with a heavy-tailed size distribution
   those can dominate the headline number. Purity is therefore reported for
   multi-transaction clients separately, and that is the figure to quote.

2. **Purity needs a null.** Even under random labels, small clients are often
   pure by chance — with 3.5% prevalence, a 3-transaction client is all-legitimate
   about 90% of the time. So "89% of clients are pure" is not evidence of anything
   on its own. ``homogeneity_null`` permutes the labels across transactions,
   holding the client size distribution fixed, and recomputes. The comparison of
   observed against that null is the actual Trap A test, and it is a stronger
   claim than the plan describes: it distinguishes clustering caused by the
   labelling rule from clustering that the size distribution would produce anyway.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fds import schema


def basic_profile(df: pd.DataFrame) -> dict[str, float | int]:
    return {
        "rows": len(df),
        "columns": int(df.shape[1]),
        "fraud_rate": float(df[schema.TARGET].mean()),
        "n_fraud": int(df[schema.TARGET].sum()),
        "first_day": int(df[schema.DAY].min()),
        "last_day": int(df[schema.DAY].max()),
        "memory_mb": float(df.memory_usage(deep=True).sum() / 1e6),
    }


def missingness(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    present = [c for c in columns if c in df.columns]
    miss = df[present].isna().mean().sort_values(ascending=False)
    return miss.rename_axis("column").rename("missing_share").reset_index()


def cardinality(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    rows = [
        {"column": c, "n_distinct": int(df[c].nunique(dropna=True))}
        for c in columns
        if c in df.columns
    ]
    return pd.DataFrame(rows).sort_values("n_distinct", ascending=False, ignore_index=True)


def entity_degree_distribution(df: pd.DataFrame, column: str) -> dict[str, float]:
    """Transactions per distinct value — the input to the hub-pruning band.

    plan.md requires the band to be a chosen, reported parameter rather than an
    auto-derived one, so this prints the distribution and a human picks. The top
    values matter most: ``gmail.com`` linking a large share of the dataset is the
    failure mode that collapses community detection into one blob.
    """
    counts = df[column].value_counts(dropna=True)
    if counts.empty:
        return {"n_distinct": 0}
    total = int(counts.sum())
    return {
        "n_distinct": int(counts.size),
        "max_degree": int(counts.iloc[0]),
        "top_value_share": float(counts.iloc[0] / total),
        "top10_share": float(counts.iloc[:10].sum() / total),
        "median_degree": float(counts.median()),
        "p90_degree": float(counts.quantile(0.90)),
        "p99_degree": float(counts.quantile(0.99)),
        "share_degree_1": float((counts == 1).sum() / counts.size),
        "share_degree_gt_1000": float((counts > 1000).sum() / counts.size),
    }


def _purity(uid: pd.Series, y: pd.Series) -> pd.DataFrame:
    frame = pd.DataFrame({"uid": uid.to_numpy(), "y": y.to_numpy()})
    grouped = frame.groupby("uid", observed=True)["y"]
    out = pd.DataFrame({"size": grouped.size(), "n_fraud": grouped.sum()})
    out["is_pure"] = (out["n_fraud"] == 0) | (out["n_fraud"] == out["size"])
    out["is_all_fraud"] = out["n_fraud"] == out["size"]
    return out


def label_homogeneity(uid: pd.Series, y: pd.Series, min_size: int = 2) -> dict[str, float | int]:
    """Measure how strongly labels cluster on reconstructed client identity."""
    per_client = _purity(uid, y)
    multi = per_client[per_client["size"] >= min_size]

    n_fraud_total = int(per_client["n_fraud"].sum())
    fraud_in_all_fraud = int(per_client.loc[per_client["is_all_fraud"], "n_fraud"].sum())

    result: dict[str, float | int] = {
        "n_clients": len(per_client),
        "n_singleton_clients": int((per_client["size"] == 1).sum()),
        "pure_share_all_clients": float(per_client["is_pure"].mean()),
        f"n_clients_size_ge_{min_size}": len(multi),
    }
    if len(multi):
        result |= {
            f"pure_share_size_ge_{min_size}": float(multi["is_pure"].mean()),
            f"all_fraud_share_size_ge_{min_size}": float(multi["is_all_fraud"].mean()),
            f"mixed_share_size_ge_{min_size}": float(1 - multi["is_pure"].mean()),
        }
    result["fraud_share_inside_all_fraud_clients"] = (
        float(fraud_in_all_fraud / n_fraud_total) if n_fraud_total else 0.0
    )
    return result


def homogeneity_null(
    uid: pd.Series,
    y: pd.Series,
    *,
    rng: np.random.Generator,
    n_permutations: int = 20,
    min_size: int = 2,
) -> dict[str, float]:
    """Purity expected under random labels, holding client sizes fixed.

    This is what makes the observed number interpretable. Labels are permuted
    across transactions, so prevalence and the client size distribution are
    preserved and only the association between client and label is destroyed.
    """
    key = f"pure_share_size_ge_{min_size}"
    labels = y.to_numpy().copy()
    samples = []
    for _ in range(n_permutations):
        rng.shuffle(labels)
        stats = label_homogeneity(uid, pd.Series(labels, index=y.index), min_size=min_size)
        if key in stats:
            samples.append(stats[key])

    if not samples:
        return {}
    arr = np.asarray(samples, dtype=float)
    return {
        f"null_mean_{key}": float(arr.mean()),
        f"null_std_{key}": float(arr.std(ddof=1)) if arr.size > 1 else 0.0,
        f"null_min_{key}": float(arr.min()),
        f"null_max_{key}": float(arr.max()),
        "n_permutations": n_permutations,
    }


def client_degree_distribution(
    entity: pd.Series, uid: pd.Series, thresholds: tuple[int, ...] = (50, 100, 500, 1000, 5000)
) -> dict[str, float | int | dict]:
    """Distinct *clients* per entity value — the correct hub measure.

    ``entity_degree_distribution`` counts transactions, but the projection the
    plan runs community detection over is client-to-client (§Part 3). An entity
    linking 40,000 transactions that belong to 40,000 separate clients is a hub;
    one linking 40,000 transactions from 12 clients is a signal. Only the client
    count distinguishes them, and the pruning band is applied to this.

    The ``survival`` block answers the question that actually decides the band:
    at a given ceiling, how many entity values remain, and what share of clients
    still has at least one usable link? A ceiling that prunes the giant component
    but strands most clients has not helped.
    """
    # The population denominator must be counted BEFORE dropping rows with no
    # value for this entity. Counting after makes each entity's coverage a share
    # of its own sub-population, so card1 (present for nearly every client) and
    # DeviceInfo (present for 29% of them) get silently different denominators
    # and cannot be compared — which is exactly the error that made card1 look
    # like a backbone.
    n_clients_total = int(pd.Series(uid.to_numpy()).nunique())

    frame = pd.DataFrame({"entity": entity.to_numpy(), "uid": uid.to_numpy()}).dropna()
    per_entity = frame.groupby("entity", observed=True)["uid"].nunique()
    if per_entity.empty:
        return {"n_values": 0}
    survival = {}
    for ceiling in thresholds:
        keep = per_entity[(per_entity >= 2) & (per_entity <= ceiling)]
        linked = frame[frame["entity"].isin(keep.index)]
        survival[str(ceiling)] = {
            "n_entity_values": int(keep.size),
            "client_coverage": float(linked["uid"].nunique() / n_clients_total),
            "max_client_degree_kept": int(keep.max()) if keep.size else 0,
        }

    return {
        "n_values": int(per_entity.size),
        "n_clients_total": n_clients_total,
        "n_clients_with_value": int(frame["uid"].nunique()),
        "max_client_degree": int(per_entity.max()),
        "median_client_degree": float(per_entity.median()),
        "p99_client_degree": float(per_entity.quantile(0.99)),
        "share_degree_1": float((per_entity == 1).sum() / per_entity.size),
        "survival": survival,
    }


def fraud_cooccurrence(
    entity: pd.Series,
    uid: pd.Series,
    client_label: pd.Series,
    *,
    rng: np.random.Generator,
    min_clients: int = 2,
    max_clients: int = 1000,
    n_permutations: int = 25,
    thresholds: tuple[int, ...] = (2, 3),
) -> dict[str, float | int]:
    """Does this entity group fraud clients together beyond chance?

    This is the measurement that decides whether an attribute can carry a
    cross-client ring signal, and it is deliberately not label concordance.
    Concordance scores an all-legitimate group exactly as highly as an all-fraud
    one, and a ring detector cares only about the second.

    The null permutes client labels **within this entity's own linked client
    subpopulation**. Permuting across all clients instead would compare, say,
    device-bearing clients against the global fraud rate — and since clients that
    carry a device record are roughly five times fraudier to begin with, pure
    selection would masquerade as edge structure. Holding the subpopulation rate
    and the group size distribution fixed isolates the structure.

    A significantly *negative* result is meaningful too: it means the attribute
    disperses fraud clients across groups, making it worse than useless as a
    linking edge.
    """
    pairs = pd.DataFrame({"entity": entity.to_numpy(), "uid": uid.to_numpy()}).dropna()
    pairs = pairs.drop_duplicates()
    sizes = pairs.groupby("entity", observed=True)["uid"].nunique()
    keep = sizes[(sizes >= min_clients) & (sizes <= max_clients)].index
    pairs = pairs[pairs["entity"].isin(keep)]
    if pairs.empty:
        return {"n_groups": 0}

    sub_index = pairs["uid"].unique()
    sub = client_label.loc[sub_index]
    codes = pd.Categorical(pairs["entity"]).codes
    n_groups = int(codes.max()) + 1

    def counts(labels: pd.Series) -> dict[int, int]:
        y = pairs["uid"].map(labels).to_numpy()
        per_group = np.bincount(codes, weights=y, minlength=n_groups)
        return {t: int((per_group >= t).sum()) for t in thresholds}

    observed = counts(sub)
    shuffled = sub.to_numpy().copy()
    draws: dict[int, list[int]] = {t: [] for t in thresholds}
    for _ in range(n_permutations):
        rng.shuffle(shuffled)
        for t, c in counts(pd.Series(shuffled, index=sub_index)).items():
            draws[t].append(c)

    result: dict[str, float | int] = {
        "n_groups": len(keep),
        "n_client_links": len(pairs),
        "subpopulation_fraud_rate": float(sub.mean()),
    }
    for t in thresholds:
        arr = np.asarray(draws[t], dtype=float)
        sd = float(arr.std(ddof=1)) if arr.size > 1 else 0.0
        result[f"groups_ge_{t}_fraud_observed"] = observed[t]
        result[f"groups_ge_{t}_fraud_null_mean"] = float(arr.mean())
        result[f"groups_ge_{t}_fraud_sd_away"] = (
            (observed[t] - float(arr.mean())) / sd if sd else 0.0
        )
    return result
