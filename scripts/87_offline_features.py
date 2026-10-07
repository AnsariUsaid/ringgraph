#!/usr/bin/env python
"""Offline (retrospective) features: label-free aggregates over every row.

See fds/offline_features.py. Test labels are never read.
"""

from __future__ import annotations

import time

from fds import paths, schema
from fds.artifacts import input_ref, read_parquet, write_parquet
from fds.cli import base_parser, record_run, resolve
from fds.ingest import load_base
from fds.offline_features import AGG_PREFIX, FE_PREFIX, GRAPH_PREFIX, base_columns, build_offline

SCHEMA_VERSION = 1


def main() -> None:
    args = base_parser(__doc__.splitlines()[0]).parse_args()
    cfg = resolve(args)
    recipe = cfg.uid.recipe_name

    df = load_base(columns=base_columns()).merge(
        read_parquet(paths.uid_map_path(recipe)), on=schema.KEY, validate="one_to_one"
    )
    started = time.perf_counter()
    table = build_offline(df)
    print(f"built {table.shape[1] - 1} features in {time.perf_counter() - started:.0f}s")
    for name, prefix in (("frequency", FE_PREFIX), ("client aggregates", AGG_PREFIX), ("graph structure", GRAPH_PREFIX)):
        print(f"  {name:<18}{sum(c.startswith(prefix) for c in table.columns):>5} columns")
    out = paths.DATA_ROOT / "offline" / f"recipe={recipe}" / "offline.parquet"
    write_parquet(table, out, schema_version=SCHEMA_VERSION, inputs=[input_ref(paths.BASE_TRANSACTIONS)])
    print(f"wrote {out}")
    record_run(cfg, script="87_offline_features")


if __name__ == "__main__":
    main()
