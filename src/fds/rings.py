"""Ring catalogue -- plan.md Part 5's four scoring axes, computed and ranked.

This is what the frontend surfaces as the "risk basis" for a flagged cluster.
Computed over the full period rather than per snapshot: it is a presentation
artefact for investigating detected rings, not a model input, so the Trap B
discipline that governs fds.structural does not apply. Nothing here is ever
joined back into a model matrix.

**Fraud counts are attached for display only.** They come from parquet, never
from the graph, and they are excluded from the composite score -- a ring's rank
must be earned by its structure, or the demo is just showing the answer key.
"""

from __future__ import annotations

import networkx as nx
import numpy as np
import pandas as pd

from fds.community_features import _max_window_share
from fds.links import LinkParams, build_links
from fds.schema import AMOUNT, DAY, KEY, TARGET, UID
from fds.synchrony import coincidence_count, shift_null

AXES = ("density", "synchrony", "concentration", "tightness")


def detect_rings(
    df: pd.DataFrame, *, link_columns: tuple[str, ...], params: LinkParams, seed: int = 42
) -> tuple[pd.DataFrame, nx.Graph]:
    """Leiden-style community detection over the client projection."""
    edges = build_links(df, UID, columns=link_columns, params=params)
    graph = nx.Graph()
    for a, b, weight, attributes in zip(
        edges["a"], edges["b"], edges["weight"], edges["attributes"], strict=True
    ):
        graph.add_edge(a, b, weight=int(weight), attributes=attributes)

    communities = nx.community.louvain_communities(graph, weight="weight", seed=seed)
    rows = [
        {"ring_id": index, UID: member}
        for index, members in enumerate(communities)
        if len(members) >= 3
        for member in members
    ]
    return pd.DataFrame(rows), graph


def score_rings(
    membership: pd.DataFrame,
    graph: nx.Graph,
    df: pd.DataFrame,
    *,
    rng: np.random.Generator,
    attribute_columns: tuple[str, ...] = (),
    n_permutations: int = 30,
) -> pd.DataFrame:
    """Score every ring on the four axes and combine into a composite rank.

    Each axis is converted to a percentile *within this catalogue* before
    combining, so one axis on a wide scale cannot dominate the composite. That
    also makes the risk-signature glyph readable: bar heights are comparable
    across axes by construction.
    """
    span = float(df["TransactionDT"].max() - df["TransactionDT"].min())
    by_client = df.groupby(UID, observed=True)

    rows = []
    for ring_id, block in membership.groupby("ring_id"):
        members = block[UID].tolist()
        size = len(members)
        subgraph = graph.subgraph(members)
        possible = size * (size - 1) / 2

        events = df[df[UID].isin(members)]
        times = events["TransactionDT"].to_numpy(dtype=float)
        codes = pd.factorize(events[UID])[0]

        observed = coincidence_count(times, codes, 3600.0)
        null = float(
            np.mean([shift_null(times, codes, 3600.0, span, rng) for _ in range(n_permutations)])
        )
        synchrony = float(observed / null) if null > 0 else float(observed > 0)

        # Part 5 asks "how few distinct devices serve how many distinct clients",
        # so this must count attribute *values*, not attribute types. Counting
        # types made the axis degenerate: with a weight-1 link floor most rings
        # share exactly one type, so concentration collapsed to ring size and
        # the composite was ranking on size twice.
        member_rows = events[list(attribute_columns)] if attribute_columns else None
        distinct_attributes = 0
        if member_rows is not None:
            for column in attribute_columns:
                counts = (
                    events.groupby(column, observed=True)[UID].nunique()
                    if column in events.columns
                    else pd.Series(dtype=int)
                )
                distinct_attributes += int((counts >= 2).sum())
        amounts = events[AMOUNT].to_numpy(dtype=float)
        cv = float(np.std(amounts) / np.mean(amounts)) if np.mean(amounts) > 0 else 0.0

        rows.append(
            {
                "ring_id": int(ring_id),
                "n_clients": size,
                "n_transactions": len(events),
                "first_day": int(events[DAY].min()),
                "last_day": int(events[DAY].max()),
                "span_days": int(events[DAY].max() - events[DAY].min()),
                "total_amount": float(amounts.sum()),
                "density": float(subgraph.number_of_edges() / possible) if possible else 0.0,
                "synchrony": synchrony,
                "burst_share": _max_window_share(times),
                "concentration": float(size / distinct_attributes) if distinct_attributes else 0.0,
                "tightness": float(1.0 / (1.0 + cv)),
                "mean_edge_weight": float(
                    np.mean([d["weight"] for _, _, d in subgraph.edges(data=True)] or [0])
                ),
                "n_fraud_clients": int(by_client[TARGET].max().reindex(members).fillna(0).sum()),
            }
        )

    rings = pd.DataFrame(rows)
    if rings.empty:
        return rings

    for axis in AXES:
        rings[f"pct_{axis}"] = rings[axis].rank(pct=True)
    rings["composite"] = rings[[f"pct_{a}" for a in AXES]].mean(axis=1)
    rings["fraud_share"] = rings["n_fraud_clients"] / rings["n_clients"]
    return rings.sort_values("composite", ascending=False, ignore_index=True)


def member_detail(membership: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    joined = df.merge(membership, on=UID)
    grouped = joined.groupby(["ring_id", UID], observed=True)
    out = pd.DataFrame(
        {
            "n_transactions": grouped.size(),
            "total_amount": grouped[AMOUNT].sum(),
            "first_day": grouped[DAY].min(),
            "last_day": grouped[DAY].max(),
            "is_fraud": grouped[TARGET].max(),
        }
    ).reset_index()
    return out


def shared_attributes(
    membership: pd.DataFrame, df: pd.DataFrame, link_columns: tuple[str, ...]
) -> pd.DataFrame:
    """Which attribute values each ring member carries -- the presence matrix."""
    joined = df.merge(membership, on=UID)
    frames = []
    for column in link_columns:
        if column not in joined.columns:
            continue
        block = joined[["ring_id", UID, column]].dropna(subset=[column])
        if block.empty:
            continue
        block = block.assign(type=column, value=block[column].astype(str))
        frames.append(block[["ring_id", UID, "type", "value"]])
    if not frames:
        return pd.DataFrame(columns=["ring_id", UID, "type", "value"])
    stacked = pd.concat(frames, ignore_index=True).drop_duplicates()

    # Keep only values shared by at least two members -- a value unique to one
    # client explains nothing about why the ring is a ring.
    counts = stacked.groupby(["ring_id", "type", "value"], observed=True)[UID].transform("nunique")
    return stacked[counts >= 2].reset_index(drop=True)


def ring_events(membership: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    """Per-transaction rows for the temporal strip."""
    joined = df.merge(membership, on=UID)
    return joined[["ring_id", UID, KEY, "TransactionDT", DAY, AMOUNT, TARGET]].rename(
        columns={TARGET: "is_fraud"}
    )
