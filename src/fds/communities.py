"""Community detection over the client-to-client projection.

plan.md is explicit that Louvain must not run on the raw bipartite
transaction-entity graph: communities there are not interpretable as candidate
rings. It runs on the ``LINKED`` projection, whose edges are cross-client by
construction — which is exactly what the revised thesis rests on (D-36).

Leiden is used where available. It is preferred over Louvain because Louvain can
produce internally disconnected communities, which for a ring inventory means a
"ring" whose members are not actually all connected to each other.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from fds.graphdb import driver

GRAPH_NAME = "client_links"


def drop_projection(name: str = GRAPH_NAME) -> None:
    with driver() as (drv, database), drv.session(database=database) as session:
        session.run(
            "CALL gds.graph.exists($name) YIELD exists "
            "WITH exists WHERE exists "
            "CALL gds.graph.drop($name) YIELD graphName RETURN graphName",
            {"name": name},
        ).consume()


def project(name: str = GRAPH_NAME, min_weight: int = 1) -> dict[str, Any]:
    """Project Client nodes and LINKED edges as an undirected weighted graph.

    Undirected because the projection is symmetric: sharing attributes has no
    direction, and Leiden requires it.
    """
    drop_projection(name)
    # Directed match: MERGE stored one relationship per pair, and matching with
    # an undirected pattern would return each of them twice, doubling the
    # projected relationship count before `undirectedRelationshipTypes` doubles
    # it again.
    query = """
    MATCH (a:Client)-[r:LINKED]->(b:Client)
    WHERE r.weight >= $min_weight
    WITH gds.graph.project($name, a, b,
        {relationshipProperties: {weight: r.weight}},
        {undirectedRelationshipTypes: ['*']}
    ) AS g
    RETURN g.graphName AS graph, g.nodeCount AS nodes, g.relationshipCount AS relationships
    """
    with driver() as (drv, database), drv.session(database=database) as session:
        return session.run(query, {"name": name, "min_weight": min_weight}).single().data()


def leiden(name: str = GRAPH_NAME, gamma: float = 1.0, max_levels: int = 10) -> pd.DataFrame:
    """Run Leiden and return one row per client with its community id."""
    query = """
    CALL gds.leiden.stream($name, {
        relationshipWeightProperty: 'weight',
        gamma: $gamma,
        maxLevels: $max_levels,
        randomSeed: 42,
        concurrency: 1
    })
    YIELD nodeId, communityId
    RETURN gds.util.asNode(nodeId).uid AS uid, communityId
    """
    with driver() as (drv, database), drv.session(database=database) as session:
        rows = session.run(query, {"name": name, "gamma": gamma, "max_levels": max_levels}).data()
    return pd.DataFrame(rows)


def write_communities(assignments: pd.DataFrame) -> int:
    """Persist community ids onto Client nodes so the API can query them."""
    rows = assignments.to_dict("records")
    written = 0
    with driver() as (drv, database), drv.session(database=database) as session:
        for start in range(0, len(rows), 10_000):
            chunk = rows[start : start + 10_000]
            session.run(
                "UNWIND $rows AS row "
                "MATCH (c:Client {uid: row.uid}) SET c.community = row.communityId",
                {"rows": chunk},
            )
            written += len(chunk)
    return written


def community_profile(assignments: pd.DataFrame) -> dict[str, Any]:
    sizes = assignments.groupby("communityId").size()
    total = int(sizes.sum())
    return {
        "n_communities": int(sizes.size),
        "n_clients": total,
        "largest_community": int(sizes.max()),
        "largest_community_share": float(sizes.max() / total),
        "median_size": float(sizes.median()),
        "n_communities_ge_3": int((sizes >= 3).sum()),
        "n_communities_ge_5": int((sizes >= 5).sum()),
    }
