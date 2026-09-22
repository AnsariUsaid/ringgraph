#!/usr/bin/env python
"""Load the client/attribute graph into Neo4j.

Loads only clients that carry at least one identity attribute: those are the
clients the cross-client thesis is about, and the rest would add ~150k isolated
nodes that no query touches.

Fraud labels are deliberately not loaded (see fds.graph_load).
"""

from __future__ import annotations

import time

from fds import paths, schema
from fds.artifacts import read_parquet
from fds.cli import base_parser, record_run, resolve
from fds.graph_load import (
    apply_schema,
    build_attribute_frames,
    build_client_frame,
    graph_counts,
    load_attributes,
    load_clients,
    load_has_attribute,
    load_linked,
    wipe,
)
from fds.ingest import load_base
from fds.links import LinkParams, build_links


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--recipe", default=None)
    parser.add_argument("--wipe", action="store_true", help="clear the database first")
    args = parser.parse_args()
    cfg = resolve(args)
    recipe = args.recipe or cfg.uid.recipe_name
    columns = tuple(cfg.graph.link_types)

    uid_map = read_parquet(paths.uid_map_path(recipe))
    df = load_base(columns=[schema.KEY, schema.DAY, *columns]).merge(
        uid_map, on=schema.KEY, validate="one_to_one"
    )

    # Restrict to clients carrying at least one linking attribute.
    has_any = df[list(columns)].notna().any(axis=1)
    linked_uids = set(df.loc[has_any, schema.UID])
    df = df[df[schema.UID].isin(linked_uids)]
    print(f"clients with at least one identity attribute: {len(linked_uids):,}")

    clients = build_client_frame(df)
    attributes, has_attribute = build_attribute_frames(df, columns)
    params = LinkParams(
        min_degree=cfg.graph.hub_min_degree,
        max_degree=cfg.graph.hub_max_degree,
        min_weight=cfg.graph.min_edge_weight,
    )
    linked = build_links(df, schema.UID, columns=columns, params=params)

    print(
        f"  to load: {len(clients):,} clients, {len(attributes):,} attributes, "
        f"{len(has_attribute):,} HAS_ATTRIBUTE, {len(linked):,} LINKED"
    )

    if args.wipe:
        print("wiping existing graph")
        wipe()
    apply_schema()

    started = time.perf_counter()
    for label, fn, frame in (
        ("clients", load_clients, clients),
        ("attributes", load_attributes, attributes),
        ("HAS_ATTRIBUTE", load_has_attribute, has_attribute),
        ("LINKED", load_linked, linked),
    ):
        if frame.empty:
            continue
        t0 = time.perf_counter()
        n = fn(frame)
        print(f"  {label:<14} {n:>8,} rows in {time.perf_counter() - t0:6.1f}s")
    print(f"total {time.perf_counter() - started:.1f}s")

    counts = graph_counts()
    print("\n-- in database --")
    for key, value in counts.items():
        print(f"  {key:<16} {value:,}")
    record_run(cfg, script="61_load_graph", metrics=counts)


if __name__ == "__main__":
    main()
