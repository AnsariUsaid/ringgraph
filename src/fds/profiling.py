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
    return miss.rename("missing_share").reset_index(names="column")


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
