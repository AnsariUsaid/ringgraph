"""Load the client/attribute graph into Neo4j.

**Labels are deliberately not loaded.** plan.md forbids any feature derived from
neighbours' labels ("Never compute community fraud rate ... it will produce a
spectacular, worthless result"). Keeping ``isFraud`` out of the database entirely
makes that a structural guarantee rather than a rule someone has to remember: a
Cypher query cannot leak a label that is not there. The API joins labels from
parquet when the frontend needs to display them.

Relationships carry ``first_day`` — the earliest day on which the client-attribute
pair was observed. That is what lets one loaded graph serve every snapshot: a
snapshot ending at day *E* is the subgraph of relationships with
``first_day < E``. Note this supports *projection*, not pruning — the degree band
must still be applied per snapshot (D-07), which ``fds.links`` does in Python
where the Trap B guarantee lives.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from fds import schema
from fds.graphdb import driver

BATCH_SIZE = 10_000

CONSTRAINTS = [
    "CREATE CONSTRAINT client_uid IF NOT EXISTS FOR (c:Client) REQUIRE c.uid IS UNIQUE",
    "CREATE CONSTRAINT attr_key IF NOT EXISTS FOR (a:Attribute) REQUIRE a.key IS UNIQUE",
]
INDEXES = [
    "CREATE INDEX attr_type IF NOT EXISTS FOR (a:Attribute) ON (a.type)",
    "CREATE INDEX client_first_day IF NOT EXISTS FOR (c:Client) ON (c.first_day)",
    "CREATE INDEX has_attr_first_day IF NOT EXISTS FOR ()-[r:HAS_ATTRIBUTE]-() ON (r.first_day)",
]


def _execute(query: str, parameters: dict[str, Any] | None = None) -> None:
    with driver() as (drv, database), drv.session(database=database) as session:
        session.run(query, parameters or {})


def _write_batches(query: str, rows: list[dict[str, Any]], batch_size: int = BATCH_SIZE) -> int:
    """Send rows through UNWIND in batches.

    One transaction per batch: a single transaction over hundreds of thousands of
    rows would exhaust the 1GB heap this instance is configured with.
    """
    written = 0
    with driver() as (drv, database), drv.session(database=database) as session:
        for start in range(0, len(rows), batch_size):
            chunk = rows[start : start + batch_size]
            session.run(query, {"rows": chunk})
            written += len(chunk)
    return written


def apply_schema() -> None:
    """Constraints and indexes before any data — they make MERGE fast, not slow."""
    for statement in CONSTRAINTS + INDEXES:
        _execute(statement)


def wipe() -> None:
    """Remove all nodes and relationships, leaving constraints in place."""
    _execute("MATCH (n) CALL (n) { DETACH DELETE n } IN TRANSACTIONS OF 10000 ROWS")


def load_clients(clients: pd.DataFrame) -> int:
    """``clients`` needs ``uid``, ``first_day``, ``n_transactions``."""
    rows = clients.to_dict("records")
    return _write_batches(
        """
        UNWIND $rows AS row
        MERGE (c:Client {uid: row.uid})
        SET c.first_day = row.first_day,
            c.n_transactions = row.n_transactions
        """,
        rows,
    )


def load_attributes(attributes: pd.DataFrame) -> int:
    """``attributes`` needs ``key`` (type-prefixed), ``type``, ``value``."""
    rows = attributes.to_dict("records")
    return _write_batches(
        """
        UNWIND $rows AS row
        MERGE (a:Attribute {key: row.key})
        SET a.type = row.type, a.value = row.value
        """,
        rows,
    )


def load_has_attribute(edges: pd.DataFrame) -> int:
    """``edges`` needs ``uid``, ``key``, ``type``, ``first_day``, ``n_transactions``."""
    rows = edges.to_dict("records")
    return _write_batches(
        """
        UNWIND $rows AS row
        MATCH (c:Client {uid: row.uid})
        MATCH (a:Attribute {key: row.key})
        MERGE (c)-[r:HAS_ATTRIBUTE]->(a)
        SET r.type = row.type,
            r.first_day = row.first_day,
            r.n_transactions = row.n_transactions
        """,
        rows,
    )


def load_linked(edges: pd.DataFrame) -> int:
    """Materialise the client-to-client projection.

    plan.md is explicit that community detection must run on this projection
    rather than the raw bipartite graph, because communities over a
    transaction-entity graph are not interpretable as candidate rings.
    """
    rows = edges.rename(columns={"a": "source", "b": "target"}).to_dict("records")
    return _write_batches(
        """
        UNWIND $rows AS row
        MATCH (a:Client {uid: row.source})
        MATCH (b:Client {uid: row.target})
        MERGE (a)-[r:LINKED]-(b)
        SET r.weight = row.weight, r.attributes = row.attributes
        """,
        rows,
    )


def build_client_frame(df: pd.DataFrame) -> pd.DataFrame:
    grouped = df.groupby(schema.UID, observed=True)[schema.DAY]
    return pd.DataFrame(
        {"first_day": grouped.min().astype(int), "n_transactions": grouped.size()}
    ).reset_index(names="uid")


def build_attribute_frames(
    df: pd.DataFrame, columns: tuple[str, ...]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Attribute nodes and client-attribute edges, with first-seen days.

    Keys are type-prefixed (``DeviceInfo:MacOS``) so two attributes that happen to
    share a raw value can never collide into one node.
    """
    node_rows, edge_rows = [], []
    for column in columns:
        if column not in df.columns:
            continue
        block = df[[schema.UID, column, schema.DAY]].dropna(subset=[column])
        if block.empty:
            continue
        block = block.assign(value=block[column].astype(str))
        grouped = block.groupby([schema.UID, "value"], observed=True)[schema.DAY]
        edges = pd.DataFrame(
            {"first_day": grouped.min().astype(int), "n_transactions": grouped.size()}
        ).reset_index()
        edges["type"] = column
        edges["key"] = column + ":" + edges["value"]
        edge_rows.append(edges.rename(columns={schema.UID: "uid"}))

        values = block["value"].drop_duplicates()
        node_rows.append(
            pd.DataFrame({"value": values, "type": column, "key": column + ":" + values})
        )

    nodes = pd.concat(node_rows, ignore_index=True) if node_rows else pd.DataFrame()
    edges_out = pd.concat(edge_rows, ignore_index=True) if edge_rows else pd.DataFrame()
    return nodes, edges_out[["uid", "key", "type", "first_day", "n_transactions"]]


def graph_counts() -> dict[str, int]:
    with driver() as (drv, database), drv.session(database=database) as session:
        return {
            "clients": session.run("MATCH (c:Client) RETURN count(c) AS n").single()["n"],
            "attributes": session.run("MATCH (a:Attribute) RETURN count(a) AS n").single()["n"],
            "has_attribute": session.run(
                "MATCH ()-[r:HAS_ATTRIBUTE]->() RETURN count(r) AS n"
            ).single()["n"],
            "linked": session.run("MATCH ()-[r:LINKED]-() RETURN count(r)/2 AS n").single()["n"],
        }
