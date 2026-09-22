#!/usr/bin/env python
"""Build structural features per snapshot and attach them time-respectingly.

This is the Trap B pipeline in anger. For each snapshot boundary the graph is
rebuilt from that snapshot's transactions alone, the degree band is applied to
degrees measured *inside* the snapshot, and the features carry a measured
max_source_day. Attachment then joins each transaction to the most recent
snapshot that predates it, and the runtime guard raises if any row ends up with
a feature derived from its own future.

Writes per-snapshot feature files and the attachment table, both of which the
plan treats as cacheable artefacts.
"""

from __future__ import annotations

import time

import pandas as pd

from fds import paths, schema
from fds.artifacts import input_ref, write_parquet
from fds.cli import base_parser, record_run, resolve
from fds.ingest import load_base
from fds.links import LinkParams
from fds.snapshots import (
    HAS_STRUCTURE,
    PROVENANCE_COLUMNS,
    attach_structural_features,
    snapshot_schedule,
)
from fds.structural import feature_columns, snapshot_feature_table

SNAPFEAT_SCHEMA_VERSION = 1
ATTACH_SCHEMA_VERSION = 1


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--recipe", default=None)
    args = parser.parse_args()
    cfg = resolve(args)
    recipe = args.recipe or cfg.uid.recipe_name
    link_columns = tuple(cfg.graph.link_types)

    uid_map = pd.read_parquet(paths.uid_map_path(recipe))
    base = load_base(columns=[schema.KEY, schema.DAY, *link_columns]).merge(
        uid_map, on=schema.KEY, validate="one_to_one"
    )

    specs = snapshot_schedule(cfg.snapshots.cadence_days, cfg.snapshots.first_end_day)
    params = LinkParams(
        min_degree=cfg.graph.hub_min_degree,
        max_degree=cfg.graph.hub_max_degree,
        min_weight=cfg.graph.min_edge_weight,
    )
    print(
        f"{len(specs)} snapshots, cadence {cfg.snapshots.cadence_days}d, "
        f"degree band {params.min_degree}-{params.max_degree}, min weight {params.min_weight}"
    )

    started = time.perf_counter()
    table = snapshot_feature_table(base, specs, link_columns=link_columns, params=params)
    print(f"built in {(time.perf_counter() - started) / 60:.1f} min")

    features = feature_columns(table)
    for spec in specs:
        block = table[table["snapshot_id"] == spec.snapshot_id]
        if block.empty:
            continue
        write_parquet(
            block,
            paths.snapfeat_dir(recipe, params.min_degree, params.max_degree, spec.end_day_exclusive)
            / "part.parquet",
            schema_version=SNAPFEAT_SCHEMA_VERSION,
            params={"recipe": recipe, "snapshot": spec.snapshot_id, **vars(params)},
            inputs=[input_ref(paths.BASE_TRANSACTIONS)],
        )

    print("\nattaching to transactions (strictly-before join)")
    attached = attach_structural_features(
        base[[schema.KEY, schema.DAY, schema.UID]], table, feature_columns=features
    )
    coverage = float(attached[HAS_STRUCTURE].mean())
    linked = float((attached["st_degree"].fillna(0) > 0).mean())
    print(f"  rows with a usable snapshot : {coverage:.4f}")
    print(f"  rows with a non-zero degree : {linked:.4f}")
    print(f"  rows before first snapshot  : {1 - coverage:.4f} (NaN, not zero)")

    keep = [schema.KEY, schema.DAY, schema.UID, *PROVENANCE_COLUMNS, HAS_STRUCTURE, *features]
    out = paths.attach_path(
        recipe, params.min_degree, params.max_degree, cfg.snapshots.cadence_days
    )
    write_parquet(
        attached[keep],
        out,
        schema_version=ATTACH_SCHEMA_VERSION,
        params={"recipe": recipe, "cadence_days": cfg.snapshots.cadence_days, **vars(params)},
        inputs=[input_ref(paths.BASE_TRANSACTIONS)],
        extra={"has_structure_share": coverage, "features": features},
    )
    print(f"\nwrote {out}")
    record_run(
        cfg,
        script="80_snapshot_features",
        metrics={"has_structure_share": coverage, "n_features": len(features)},
    )


if __name__ == "__main__":
    main()
