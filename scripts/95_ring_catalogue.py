#!/usr/bin/env python
"""Build the ring catalogue the frontend serves.

Detects communities over the full-period client projection, scores each on
plan.md Part 5's four axes, and writes the tables the API reads: rings,
members, shared attributes and per-transaction events.

Fraud counts are attached for display only and are excluded from the composite
score. A ring must earn its rank on structure, or the demo is showing the answer
key rather than a detector.
"""

from __future__ import annotations

import time

import pandas as pd

from fds import paths, schema
from fds.artifacts import input_ref, write_parquet
from fds.cli import base_parser, record_run, resolve
from fds.ingest import load_base
from fds.links import LinkParams
from fds.rings import (
    detect_rings,
    member_detail,
    ring_events,
    score_rings,
    shared_attributes,
)
from fds.rng import rng_for

SCHEMA_VERSION = 1


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--recipe", default=None)
    args = parser.parse_args()
    cfg = resolve(args)
    recipe = args.recipe or cfg.uid.recipe_name
    link_columns = tuple(cfg.graph.link_types)

    uid_map = pd.read_parquet(paths.uid_map_path(recipe))
    df = load_base(
        columns=[
            schema.KEY,
            schema.DAY,
            schema.TIME_RAW,
            schema.AMOUNT,
            schema.TARGET,
            *link_columns,
        ]
    ).merge(uid_map, on=schema.KEY, validate="one_to_one")

    params = LinkParams(
        min_degree=cfg.graph.hub_min_degree,
        max_degree=cfg.graph.hub_max_degree,
        min_weight=cfg.graph.min_edge_weight,
    )
    print(f"detecting rings: degree band 2-{params.max_degree}, weight >= {params.min_weight}")

    started = time.perf_counter()
    membership, graph = detect_rings(df, link_columns=link_columns, params=params)
    print(
        f"  {membership['ring_id'].nunique():,} rings over "
        f"{membership[schema.UID].nunique():,} clients "
        f"({graph.number_of_edges():,} links)"
    )

    rings = score_rings(
        membership,
        graph,
        df,
        rng=rng_for("ring_scores", cfg.seed),
        attribute_columns=link_columns,
    )
    members = member_detail(membership, df)
    attributes = shared_attributes(membership, df, link_columns)
    events = ring_events(membership, df)
    print(f"scored in {(time.perf_counter() - started) / 60:.1f} min")

    paths.ensure(paths.RINGS_DIR)
    inputs = [input_ref(paths.BASE_TRANSACTIONS)]
    for name, frame in (
        ("rings", rings),
        ("members", members),
        ("attributes", attributes),
        ("events", events),
    ):
        write_parquet(
            frame,
            paths.RINGS_DIR / f"{name}.parquet",
            schema_version=SCHEMA_VERSION,
            params={"recipe": recipe, **vars(params)},
            inputs=inputs,
        )
        print(f"  {name:<12} {len(frame):>8,} rows")

    print(
        f"\n{'rank':>5}{'ring':>6}{'clients':>9}{'txns':>7}{'fraud':>7}"
        f"{'density':>9}{'sync':>8}{'conc':>7}{'tight':>7}{'score':>8}"
    )
    print("-" * 73)
    for rank, (_, r) in enumerate(rings.head(12).iterrows(), 1):
        print(
            f"{rank:>5}{int(r['ring_id']):>6}{int(r['n_clients']):>9}"
            f"{int(r['n_transactions']):>7}{int(r['n_fraud_clients']):>7}"
            f"{r['density']:>9.3f}{r['synchrony']:>8.1f}{r['concentration']:>7.2f}"
            f"{r['tightness']:>7.3f}{r['composite']:>8.3f}"
        )

    fraud_rings = int((rings["n_fraud_clients"] >= 2).sum())
    pure = int(((rings["fraud_share"] == 1.0) & (rings["n_clients"] >= 3)).sum())
    print(f"\n  rings with >=2 fraud clients: {fraud_rings:,} of {len(rings):,}")
    print(f"  entirely fraudulent rings   : {pure:,}")
    record_run(
        cfg, script="95_ring_catalogue", metrics={"n_rings": len(rings), "fraud_rings": fraud_rings}
    )


if __name__ == "__main__":
    main()
