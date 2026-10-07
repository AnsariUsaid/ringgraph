#!/usr/bin/env python
"""Delayed-label features for every delay in one table (see fds/label_features.py).

Prints how much of the test set the features touch, split by fraud/legit: that
coverage is the ceiling on what any lift can be, so it is looked at before any
model is trained.
"""

from __future__ import annotations

import pandas as pd

from fds import paths, schema
from fds.artifacts import input_ref, read_parquet, write_parquet
from fds.cli import base_parser, record_run, resolve
from fds.ingest import load_base
from fds.label_features import (
    DELAYS,
    GRAPH_PREFIX,
    CONTROL_PREFIX,
    add_device_fingerprints,
    build_label_features,
    needed_base_columns,
)
from fds.splits import Split, assign_split

SCHEMA_VERSION = 1


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    args = parser.parse_args()
    cfg = resolve(args)
    recipe = cfg.uid.recipe_name

    df = load_base(columns=needed_base_columns() + [schema.DAY])
    uid_map = read_parquet(paths.uid_map_path(recipe))
    df = df.merge(uid_map, on=schema.KEY, validate="one_to_one")
    df = add_device_fingerprints(df)

    tables = [build_label_features(df, d).set_index(schema.KEY) for d in DELAYS]
    table = pd.concat(tables, axis=1).reset_index()
    out = paths.labelfeat_path(recipe)
    write_parquet(
        table,
        out,
        schema_version=SCHEMA_VERSION,
        params={"delays": list(DELAYS), "recipe": recipe},
        inputs=[input_ref(paths.BASE_TRANSACTIONS)],
    )
    print(f"wrote {out}  ({table.shape[0]:,} rows x {table.shape[1]-1} features)")

    test = (assign_split(df[schema.DAY]) == str(Split.TEST)).to_numpy()
    y = df[schema.TARGET].to_numpy() == 1
    print(f"\n{'delay':>6}{'family':>8}{'touched fraud':>15}{'touched legit':>15}{'lift':>7}  (test rows with any confirmed-fraud exposure)")
    for d in DELAYS:
        for fam, prefix in (("ctrl", CONTROL_PREFIX), ("graph", GRAPH_PREFIX)):
            cols = [c for c in table.columns if c.startswith(f"{prefix}{d}_") and c.endswith("_conf")]
            hit = (table[cols].to_numpy() > 0).any(axis=1)
            f, l = hit[test & y].mean(), hit[test & ~y].mean()
            print(f"{d:>6}{fam:>8}{f:>15.3f}{l:>15.3f}{f / max(l, 1e-9):>7.1f}")
    record_run(cfg, script="83_label_features")


if __name__ == "__main__":
    main()
