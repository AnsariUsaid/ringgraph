"""Community-level features -- plan.md Part 5's ring-scoring axes as model inputs.

The M2 null (D-43) used *per-client* graph metrics: degree, triangles, PageRank.
Those largely re-encode what the tabular baseline already holds as categoricals,
which is why they added nothing.

This is the one remaining idea with independent evidence behind it. D-39 measured
fraud-bearing components as 3-4x more temporally synchronised than clean
components of the same size, and synchrony is currently not a model feature at
all. Part 5's other axes -- density, attribute concentration, amount tightness --
are group properties that no per-client metric captures either.

**Still no labels.** Every quantity here is a property of shape, timing or
amount. Community fraud rate and anything of that family remain forbidden.

**Burstiness is measured deterministically**, as the largest share of a
community's transactions falling inside one window, rather than by permutation.
The permutation null in fds.synchrony answers "is this more synchronised than
chance", which is the right question for a *finding*; as a per-snapshot model
feature it would cost 26 x n_communities shuffles for a number the model can
calibrate itself.
"""

from __future__ import annotations

import networkx as nx
import numpy as np
import pandas as pd

from fds.links import LinkParams, build_links
from fds.schema import AMOUNT, TIME_RAW, UID

PREFIX = "cm_"
BURST_WINDOW_SECONDS = 3600.0
LOUVAIN_SEED = 42


def _graph(edges: pd.DataFrame) -> nx.Graph:
    graph = nx.Graph()
    for a, b, weight in zip(
        edges["a"].to_numpy(), edges["b"].to_numpy(), edges["weight"].to_numpy(), strict=True
    ):
        graph.add_edge(a, b, weight=int(weight))
    return graph


def _max_window_share(times: np.ndarray, window: float = BURST_WINDOW_SECONDS) -> float:
    """Largest share of events falling inside any window of the given width.

    A coordinated burst pushes this towards 1; ordinary spread-out activity keeps
    it low. Computed with a two-pointer sweep, so it is linear after the sort.
    """
    if times.size < 2:
        return 0.0
    ordered = np.sort(times)
    right = np.searchsorted(ordered, ordered + window, side="right")
    return float((right - np.arange(ordered.size)).max() / ordered.size)


def community_table(
    source: pd.DataFrame,
    *,
    link_columns: tuple[str, ...],
    params: LinkParams,
) -> pd.DataFrame:
    """One row per client *that belongs to a community*.

    Clients with no links are simply absent from the returned frame; they pick
    up NaN later, at the ``merge_asof`` in ``attach_structural_features``. The
    outcome is what matters -- an isolated client has no group density and zero
    would assert one -- but this function does not produce the NaN itself.
    """
    edges = build_links(source, UID, columns=link_columns, params=params)
    if edges.empty:
        return pd.DataFrame(columns=[UID])

    graph = _graph(edges)
    communities = nx.community.louvain_communities(
        graph, weight="weight", seed=LOUVAIN_SEED, resolution=1.0
    )

    membership = {}
    for index, members in enumerate(communities):
        for node in members:
            membership[node] = index

    by_client = source.groupby(UID, observed=True)
    client_times = by_client[TIME_RAW].apply(lambda s: s.to_numpy(dtype=float))
    client_amounts = by_client[AMOUNT].apply(lambda s: s.to_numpy(dtype=float))
    attr_lookup = {
        column: source.groupby(UID, observed=True)[column].apply(
            lambda s: set(s.dropna().astype(str))
        )
        for column in link_columns
        if column in source.columns
    }

    rows = []
    for index, members in enumerate(communities):
        members = [m for m in members if m in client_times.index]
        size = len(members)
        if size < 2:
            continue
        subgraph = graph.subgraph(members)
        internal = subgraph.number_of_edges()
        possible = size * (size - 1) / 2
        weights = [d["weight"] for _, _, d in subgraph.edges(data=True)]

        times = np.concatenate([client_times.loc[m] for m in members])
        amounts = np.concatenate([client_amounts.loc[m] for m in members])
        distinct_attributes = sum(
            len(set().union(*(lookup.loc[m] for m in members if m in lookup.index)) or ())
            for lookup in attr_lookup.values()
        )

        rows.append(
            {
                "community": index,
                "members": members,
                f"{PREFIX}size": size,
                f"{PREFIX}density": float(internal / possible) if possible else 0.0,
                f"{PREFIX}mean_edge_weight": float(np.mean(weights)) if weights else 0.0,
                f"{PREFIX}attr_concentration": (
                    float(size / distinct_attributes) if distinct_attributes else 0.0
                ),
                f"{PREFIX}burst_share": _max_window_share(times),
                f"{PREFIX}txn_count": int(times.size),
                f"{PREFIX}amount_cv": (
                    float(np.std(amounts) / np.mean(amounts)) if np.mean(amounts) > 0 else 0.0
                ),
                f"{PREFIX}span_days": float((times.max() - times.min()) / 86_400.0),
            }
        )

    if not rows:
        return pd.DataFrame(columns=[UID])

    table = pd.DataFrame(rows)
    feature_cols = [c for c in table.columns if c.startswith(PREFIX)]
    expanded = table.explode("members").rename(columns={"members": UID})
    return expanded[[UID, *feature_cols]].reset_index(drop=True)


def feature_columns(table: pd.DataFrame) -> list[str]:
    return [c for c in table.columns if c.startswith(PREFIX)]
