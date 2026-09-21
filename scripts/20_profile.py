#!/usr/bin/env python
"""Profile the base frame: missingness, cardinality and entity degree distributions.

The degree distributions are the input to the hub-pruning band (plan.md §Part 3).
The band is chosen by a human from these numbers and reported as a parameter — an
auto-derived threshold is one nobody can defend.
"""

from __future__ import annotations

import json

from fds import paths, schema
from fds.cli import base_parser, record_run, resolve
from fds.ingest import load_base
from fds.profiling import basic_profile, cardinality, entity_degree_distribution, missingness

COLUMN_GROUPS = {
    "identity": schema.ID_NUMERIC_COLS + schema.ID_STRING_COLS + schema.DEVICE_COLS,
    "card_addr": schema.CARD_COLS + schema.ADDR_COLS,
    "counts_D": schema.D_COLS,
    "match_M": schema.M_COLS,
}


def main() -> None:
    args = base_parser(__doc__.splitlines()[0]).parse_args()
    cfg = resolve(args)
    df = load_base()

    profile = basic_profile(df)
    print("\n-- base --")
    for key, value in profile.items():
        print(f"  {key:<24} {value:,.4f}" if isinstance(value, float) else f"  {key:<24} {value:,}")

    print("\n-- entity degree distributions (hub-pruning input) --")
    degrees = {}
    for entity, column in schema.ENTITY_SOURCE_COLUMNS.items():
        if column not in df.columns:
            continue
        degrees[entity] = entity_degree_distribution(df, column)
        d = degrees[entity]
        print(
            f"  {entity:<12} {column:<16} distinct={d['n_distinct']:>7,}  "
            f"max={d['max_degree']:>7,}  top1={d['top_value_share']:.3f}  "
            f"deg1={d['share_degree_1']:.3f}"
        )

    miss = {name: missingness(df, cols).to_dict("records") for name, cols in COLUMN_GROUPS.items()}
    card = cardinality(df, list(schema.ENTITY_SOURCE_COLUMNS.values())).to_dict("records")

    out = paths.report_path("profile.json")
    paths.ensure_parent(out)
    out.write_text(
        json.dumps(
            {"base": profile, "degrees": degrees, "missingness": miss, "cardinality": card},
            indent=2,
        )
        + "\n"
    )
    print(f"\nwrote {out}")
    record_run(cfg, script="20_profile", metrics=profile)


if __name__ == "__main__":
    main()
