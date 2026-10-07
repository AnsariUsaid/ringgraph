#!/usr/bin/env python
"""Relational features (labels at delays, neighbourhood behaviour, 2-hop propagation).

See fds/relational_features.py. One table, every delay, keyed by TransactionID.
"""

from __future__ import annotations

import time

from fds import paths, schema
from fds.artifacts import input_ref, read_parquet, write_parquet
from fds.cli import base_parser, record_run, resolve
from fds.ingest import load_base
from fds.label_features import DELAYS
from fds.relational_features import base_columns, build_relational

SCHEMA_VERSION = 1


def main() -> None:
    args = base_parser(__doc__.splitlines()[0]).parse_args()
    cfg = resolve(args)
    recipe = cfg.uid.recipe_name

    df = load_base(columns=base_columns()).merge(
        read_parquet(paths.uid_map_path(recipe)), on=schema.KEY, validate="one_to_one"
    )
    started = time.perf_counter()
    table = build_relational(df, DELAYS)
    print(f"built {table.shape[1] - 1} features in {time.perf_counter() - started:.0f}s")
    for fam in ("rs_", "rl30_", "rp30_"):
        print(f"  {fam:<6}{sum(c.startswith(fam) for c in table.columns):>4} columns")

    out = paths.relfeat_path(recipe)
    write_parquet(
        table,
        out,
        schema_version=SCHEMA_VERSION,
        params={"delays": list(DELAYS), "recipe": recipe},
        inputs=[input_ref(paths.BASE_TRANSACTIONS)],
    )
    print(f"wrote {out}")
    record_run(cfg, script="84_relational_features")


if __name__ == "__main__":
    main()
