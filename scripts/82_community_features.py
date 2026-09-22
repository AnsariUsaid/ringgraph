#!/usr/bin/env python
"""Build community-level features per snapshot and attach them time-respectingly.

Same Trap B discipline as scripts/80: each snapshot's communities are detected
from that snapshot's transactions alone, with the degree band applied to
snapshot-local degrees, and the features carry a measured max_source_day.

Louvain runs in networkx rather than Neo4j here. Not a rejection of GDS -- it
keeps the whole time-respecting path in one process, where the snapshot filter
is guaranteed by fds.snapshots, rather than spread across 26 database
projections that would each need their own guarantee.
"""

from __future__ import annotations

import time

import pandas as pd

from fds import paths, schema
from fds.artifacts import input_ref, write_parquet
from fds.cli import base_parser, record_run, resolve
from fds.community_features import community_table, feature_columns
from fds.ingest import load_base
from fds.links import LinkParams
from fds.snapshots import (
    HAS_STRUCTURE,
    PROVENANCE_COLUMNS,
    attach_structural_features,
    snapshot_provenance,
    snapshot_schedule,
    transactions_for,
)

SCHEMA_VERSION = 1


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--recipe", default=None)
    args = parser.parse_args()
    cfg = resolve(args)
    recipe = args.recipe or cfg.uid.recipe_name
    link_columns = tuple(cfg.graph.link_types)

    uid_map = pd.read_parquet(paths.uid_map_path(recipe))
    base = load_base(
        columns=[schema.KEY, schema.DAY, schema.TIME_RAW, schema.AMOUNT, *link_columns]
    ).merge(uid_map, on=schema.KEY, validate="one_to_one")

    specs = snapshot_schedule(cfg.snapshots.cadence_days, cfg.snapshots.first_end_day)
    params = LinkParams(
        min_degree=cfg.graph.hub_min_degree,
        max_degree=cfg.graph.hub_max_degree,
        min_weight=cfg.graph.min_edge_weight,
    )
    print(
        f"{len(specs)} snapshots, degree band 2-{params.max_degree}, weight >= {params.min_weight}"
    )

    started = time.perf_counter()
    frames = []
    for spec in specs:
        source = transactions_for(spec, base)
        if source.empty:
            continue
        provenance = snapshot_provenance(source, spec)
        table = community_table(source, link_columns=link_columns, params=params)
        if table.empty:
            continue
        for key, value in provenance.items():
            table[key] = value
        frames.append(table)
        print(
            f"  {spec.snapshot_id}  {provenance['n_source_txns']:>7,} txns  "
            f"{len(table):>6,} clients in communities"
        )
    table = pd.concat(frames, ignore_index=True)
    print(f"built in {(time.perf_counter() - started) / 60:.1f} min")

    features = feature_columns(table)
    attached = attach_structural_features(
        base[[schema.KEY, schema.DAY, schema.UID]], table, feature_columns=features
    )
    coverage = float(attached[HAS_STRUCTURE].mean())
    print(f"\n  rows in a community at prediction time: {coverage:.4f}")

    keep = [schema.KEY, schema.DAY, schema.UID, *PROVENANCE_COLUMNS, HAS_STRUCTURE, *features]
    out = paths.attach_path(
        recipe, params.min_degree, params.max_degree, cfg.snapshots.cadence_days
    ).with_name("attach_community.parquet")
    write_parquet(
        attached[keep],
        out,
        schema_version=SCHEMA_VERSION,
        params={"recipe": recipe, "cadence_days": cfg.snapshots.cadence_days, **vars(params)},
        inputs=[input_ref(paths.BASE_TRANSACTIONS)],
        extra={"coverage": coverage, "features": features},
    )
    print(f"wrote {out}")
    record_run(cfg, script="82_community_features", metrics={"coverage": coverage})


if __name__ == "__main__":
    main()
