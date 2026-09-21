#!/usr/bin/env python
"""Build the narrow [TransactionID, uid] key table for each reconstruction recipe.

Narrow by design: writing one wide frame per recipe would triple the disk for a
single added column and create frames that can silently drift apart (D-10).
"""

from __future__ import annotations

import json

import pandas as pd

from fds import paths, schema
from fds.artifacts import input_ref, write_parquet
from fds.cli import base_parser, record_run, resolve
from fds.entities import UID_RECIPES, build_uid, client_size_diagnostics
from fds.ingest import load_base

UID_MAP_SCHEMA_VERSION = 1


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--recipes", nargs="*", default=sorted(UID_RECIPES))
    args = parser.parse_args()
    cfg = resolve(args)

    needed = {schema.KEY, schema.DAY, "D1"}
    for recipe in args.recipes:
        needed |= {c for c in UID_RECIPES[recipe].columns if c != schema.D1N}
    df = load_base(columns=sorted(needed))
    df[schema.D1N] = (df[schema.DAY] - df["D1"]).astype("Int16")

    summary = {}
    for name in args.recipes:
        recipe = UID_RECIPES[name]
        uid = build_uid(df, recipe)
        diagnostics = client_size_diagnostics(uid)
        summary[name] = diagnostics
        print(f"\n-- {name} --")
        for key, value in diagnostics.items():
            print(
                f"  {key:<26} {value:,.4f}"
                if isinstance(value, float)
                else f"  {key:<26} {value:,}"
            )

        write_parquet(
            pd.DataFrame({schema.KEY: df[schema.KEY].to_numpy(), schema.UID: uid.to_numpy()}),
            paths.uid_map_path(name),
            schema_version=UID_MAP_SCHEMA_VERSION,
            params={
                "recipe": name,
                "columns": list(recipe.columns),
                "null_policy": str(recipe.null_policy),
            },
            inputs=[input_ref(paths.BASE_TRANSACTIONS)],
            extra={"diagnostics": diagnostics},
        )

    out = paths.report_path("uid_recipes.json")
    paths.ensure_parent(out)
    out.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"\nwrote {out}")
    record_run(cfg, script="30_uid_map", metrics={"recipes": list(args.recipes)})


if __name__ == "__main__":
    main()
