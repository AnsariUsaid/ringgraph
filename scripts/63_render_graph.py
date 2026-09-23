#!/usr/bin/env python
"""Render the linked client graph as an image.

Neo4j Browser cannot usefully draw the full database: 74k nodes, and 69k of the
clients carry no LINKED edge at all, so they would render as a meaningless dust
cloud. What matters is the linked subgraph -- the 1,628 clients the cross-client
thesis is actually about.

Fraud labels come from parquet, never from the graph (D-40). They are used here
for display only.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd

from fds import paths, schema
from fds.artifacts import read_parquet
from fds.cli import base_parser, resolve
from fds.graphdb import run
from fds.ingest import load_base


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--recipe", default=None)
    parser.add_argument("--out", default="linked_graph.png")
    args = parser.parse_args()
    cfg = resolve(args)
    recipe = args.recipe or cfg.uid.recipe_name

    edges = run(
        "MATCH (a:Client)-[r:LINKED]->(b:Client) "
        "RETURN a.uid AS source, b.uid AS target, r.weight AS weight"
    )
    nodes = run(
        "MATCH (c:Client) WHERE c.community IS NOT NULL "
        "RETURN c.uid AS uid, c.community AS community, c.n_transactions AS n_txns"
    )
    node_df = pd.DataFrame(nodes)

    uid_map = read_parquet(paths.uid_map_path(recipe))
    base = load_base(columns=[schema.KEY, schema.TARGET]).merge(
        uid_map, on=schema.KEY, validate="one_to_one"
    )
    client_label = base.groupby(schema.UID, observed=True)[schema.TARGET].max()
    node_df["is_fraud"] = node_df["uid"].map(client_label).fillna(0).astype(int)

    graph = nx.Graph()
    for _, row in node_df.iterrows():
        graph.add_node(row["uid"], community=row["community"], fraud=row["is_fraud"])
    for edge in edges:
        graph.add_edge(edge["source"], edge["target"], weight=edge["weight"])

    print(f"rendering {graph.number_of_nodes():,} clients, {graph.number_of_edges():,} links")
    print(f"  fraud clients: {int(node_df['is_fraud'].sum()):,}")

    # One spring layout over the whole graph. networkx places disconnected
    # components on a shared canvas without packing them, so the hundreds of
    # small rings spread out on their own -- which is adequate here only because
    # the graph is already shattered. It would not be if the graph percolated.
    pos = nx.spring_layout(graph, k=0.35, iterations=60, seed=42)

    fig, ax = plt.subplots(figsize=(20, 20), facecolor="#0B0E14")
    ax.set_facecolor("#0B0E14")

    nx.draw_networkx_edges(graph, pos, ax=ax, edge_color="#3A4453", width=0.6, alpha=0.5)

    fraud_nodes = [n for n in graph if graph.nodes[n]["fraud"] == 1]
    clean_nodes = [n for n in graph if graph.nodes[n]["fraud"] == 0]
    nx.draw_networkx_nodes(
        graph,
        pos,
        nodelist=clean_nodes,
        ax=ax,
        node_size=26,
        node_color="#7AA7FF",
        alpha=0.75,
        linewidths=0,
    )
    nx.draw_networkx_nodes(
        graph,
        pos,
        nodelist=fraud_nodes,
        ax=ax,
        node_size=64,
        node_color="#F04E4E",
        alpha=0.95,
        linewidths=0.6,
        edgecolors="#FFD0D0",
    )

    ax.set_title(
        f"Cross-client link graph  ·  {graph.number_of_nodes():,} clients  ·  "
        f"{graph.number_of_edges():,} shared-device links  ·  "
        f"{len(fraud_nodes):,} fraudulent (red)",
        color="#E6EAF2",
        fontsize=17,
        pad=22,
    )
    ax.axis("off")
    fig.tight_layout()

    out = paths.report_path(args.out)
    paths.ensure_parent(out)
    fig.savefig(out, dpi=110, facecolor="#0B0E14", bbox_inches="tight")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
