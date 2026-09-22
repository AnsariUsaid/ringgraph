"""Structural features, computed per snapshot and attached time-respectingly.

plan.md §Part 4. Every feature here is a property of graph *shape* — degree,
triangles, clustering, PageRank, component and community size. None of them
touches a label.

**The prohibition that matters:** no feature may be derived from neighbours'
labels. No community fraud rate, no "share of linked clients that were
fraudulent", nothing of that family. It is direct leakage and would produce a
spectacular, worthless result. This is enforced twice over: labels are not in
Neo4j at all (D-40), and this module never receives a label column.

**The Trap B discipline:** each snapshot's features are built from
``transactions_for(spec, base)`` and nothing else, and the degree band is applied
to degrees measured *inside* that snapshot. Ranking entities by a global degree
would decide what to prune at day 30 using day-180 data — a forward leak in the
topology that no row-level timestamp check could see (D-07).
"""

from __future__ import annotations

import networkx as nx
import pandas as pd

from fds.links import LinkParams, build_links
from fds.schema import UID
from fds.snapshots import SnapshotSpec, snapshot_provenance, transactions_for

FEATURE_PREFIX = "st_"


def _graph_from_edges(edges: pd.DataFrame) -> nx.Graph:
    graph = nx.Graph()
    if edges.empty:
        return graph
    for a, b, weight in zip(
        edges["a"].to_numpy(), edges["b"].to_numpy(), edges["weight"].to_numpy(), strict=True
    ):
        graph.add_edge(a, b, weight=int(weight))
    return graph


def structural_features(
    source: pd.DataFrame,
    *,
    link_columns: tuple[str, ...],
    params: LinkParams,
) -> pd.DataFrame:
    """Per-client graph features for one snapshot's transaction set.

    Clients present in the snapshot but carrying no links get genuine zeros —
    degree 0 and component size 1 are true statements about an isolated node.
    That is different from a client whose transactions predate every snapshot,
    which gets NaN at attachment time (D-20).
    """
    edges = build_links(source, UID, columns=link_columns, params=params)
    graph = _graph_from_edges(edges)

    clients = pd.Index(source[UID].unique(), name=UID)
    features = pd.DataFrame(index=clients)

    if graph.number_of_nodes() == 0:
        features[f"{FEATURE_PREFIX}degree"] = 0
        features[f"{FEATURE_PREFIX}weighted_degree"] = 0.0
        features[f"{FEATURE_PREFIX}triangles"] = 0
        features[f"{FEATURE_PREFIX}clustering"] = 0.0
        features[f"{FEATURE_PREFIX}two_hop_size"] = 0
        features[f"{FEATURE_PREFIX}pagerank"] = 0.0
        features[f"{FEATURE_PREFIX}component_size"] = 1
        features[f"{FEATURE_PREFIX}max_edge_weight"] = 0
        return features.reset_index()

    degree = dict(graph.degree())
    weighted = dict(graph.degree(weight="weight"))
    triangles = nx.triangles(graph)
    clustering = nx.clustering(graph)
    pagerank = nx.pagerank(graph, weight="weight")

    component_size: dict[str, int] = {}
    for component in nx.connected_components(graph):
        size = len(component)
        for node in component:
            component_size[node] = size

    two_hop = {
        node: len(set().union(*(set(graph.neighbors(n)) for n in graph.neighbors(node))) - {node})
        if degree[node]
        else 0
        for node in graph.nodes
    }
    max_weight = {
        node: max((graph[node][n]["weight"] for n in graph.neighbors(node)), default=0)
        for node in graph.nodes
    }

    features[f"{FEATURE_PREFIX}degree"] = features.index.map(degree).fillna(0).astype("int32")
    features[f"{FEATURE_PREFIX}weighted_degree"] = (
        features.index.map(weighted).fillna(0).astype("float32")
    )
    features[f"{FEATURE_PREFIX}triangles"] = features.index.map(triangles).fillna(0).astype("int32")
    features[f"{FEATURE_PREFIX}clustering"] = (
        features.index.map(clustering).fillna(0).astype("float32")
    )
    features[f"{FEATURE_PREFIX}two_hop_size"] = (
        features.index.map(two_hop).fillna(0).astype("int32")
    )
    features[f"{FEATURE_PREFIX}pagerank"] = features.index.map(pagerank).fillna(0).astype("float32")
    features[f"{FEATURE_PREFIX}component_size"] = (
        features.index.map(component_size).fillna(1).astype("int32")
    )
    features[f"{FEATURE_PREFIX}max_edge_weight"] = (
        features.index.map(max_weight).fillna(0).astype("int32")
    )
    return features.reset_index()


def snapshot_feature_table(
    base: pd.DataFrame,
    specs: list[SnapshotSpec],
    *,
    link_columns: tuple[str, ...],
    params: LinkParams,
    progress: bool = True,
) -> pd.DataFrame:
    """Build features for every snapshot, carrying measured provenance.

    ``max_source_day`` comes from ``snapshot_provenance``, which derives it from
    the rows that actually entered the graph rather than from the declared
    boundary. That is what the Trap B guard checks (D-08).
    """
    frames = []
    for spec in specs:
        source = transactions_for(spec, base)
        if source.empty:
            continue
        provenance = snapshot_provenance(source, spec)
        features = structural_features(source, link_columns=link_columns, params=params)
        for key, value in provenance.items():
            features[key] = value
        frames.append(features)
        if progress:
            linked = int((features[f"{FEATURE_PREFIX}degree"] > 0).sum())
            print(
                f"  {spec.snapshot_id}  end_day<{spec.end_day_exclusive:>4}  "
                f"{provenance['n_source_txns']:>7,} txns  "
                f"{len(features):>7,} clients  {linked:>6,} linked"
            )
    if not frames:
        raise ValueError("no snapshots produced features")
    return pd.concat(frames, ignore_index=True)


def feature_columns(table: pd.DataFrame) -> list[str]:
    return [c for c in table.columns if c.startswith(FEATURE_PREFIX)]
