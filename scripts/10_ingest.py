#!/usr/bin/env python
"""Build the immutable base frame: join the two CSVs, fix dtypes, derive day/D1n.

Produces ``data/base/transactions.parquet`` with a manifest sidecar. Every later
stage reads this file; it is written once and not rewritten.
"""

from __future__ import annotations

import sys

from fds import paths
from fds.artifacts import input_ref, write_parquet
from fds.cli import base_parser, record_run, resolve
from fds.ingest import BASE_SCHEMA_VERSION, add_derived, identity_coverage, load_raw


def main() -> None:
    args = base_parser(__doc__.splitlines()[0]).parse_args()
    cfg = resolve(args)

    if paths.BASE_TRANSACTIONS.exists() and not args.force:
        sys.exit(f"{paths.BASE_TRANSACTIONS} already exists; pass --force to rebuild")

    for source in (paths.RAW_TRANSACTION_CSV, paths.RAW_IDENTITY_CSV):
        if not source.exists():
            sys.exit(f"{source} is missing — run scripts/00_download.py first")

    print("reading and joining source tables")
    df = add_derived(load_raw(paths.RAW_TRANSACTION_CSV, paths.RAW_IDENTITY_CSV))

    coverage = identity_coverage(df)
    for key, value in coverage.items():
        print(f"  {key:<22} {value:,.4f}" if isinstance(value, float) else f"  {key:<22} {value:,}")

    write_parquet(
        df,
        paths.BASE_TRANSACTIONS,
        schema_version=BASE_SCHEMA_VERSION,
        inputs=[input_ref(paths.RAW_TRANSACTION_CSV), input_ref(paths.RAW_IDENTITY_CSV)],
        extra={"coverage": coverage},
    )
    print(f"wrote {paths.BASE_TRANSACTIONS} ({df.shape[0]:,} x {df.shape[1]})")
    record_run(cfg, script="10_ingest", metrics=coverage)


if __name__ == "__main__":
    main()
