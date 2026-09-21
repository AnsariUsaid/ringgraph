#!/usr/bin/env python
"""Choose the hub-pruning band from measured client degrees.

plan.md §Part 3 requires the band to be a reported parameter rather than an
auto-derived threshold. This script produces the evidence a human picks from:
for each linking entity, how many distinct clients it touches, and how much
client coverage survives at each candidate ceiling.

Degrees here are counted over the *whole* dataset, which is correct for choosing
a reported constant but must not be confused with the degrees the pipeline
applies — those are recomputed per snapshot (D-07), or the topology leaks the
future.
"""

from __future__ import annotations

import json

from fds import paths, schema
from fds.artifacts import read_parquet
from fds.cli import base_parser, record_run, resolve
from fds.ingest import load_base
from fds.profiling import client_degree_distribution

THRESHOLDS = (50, 100, 500, 1000, 5000)


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--recipe", default=None)
    args = parser.parse_args()
    cfg = resolve(args)
    recipe = args.recipe or cfg.uid.recipe_name

    uid_map = read_parquet(paths.uid_map_path(recipe))
    columns = [schema.KEY, *schema.ENTITY_SOURCE_COLUMNS.values()]
    df = load_base(columns=columns).merge(uid_map, on=schema.KEY, validate="one_to_one")

    results = {}
    for entity, column in schema.ENTITY_SOURCE_COLUMNS.items():
        stats = client_degree_distribution(df[column], df[schema.UID], THRESHOLDS)
        results[entity] = stats
        if not stats.get("n_values"):
            continue
        print(f"\n-- {entity} ({column}) --")
        print(
            f"  values={stats['n_values']:,}  max_client_degree={stats['max_client_degree']:,}  "
            f"median={stats['median_client_degree']:.0f}  deg1_share={stats['share_degree_1']:.3f}"
        )
        for ceiling, s in stats["survival"].items():
            print(
                f"    ceiling {ceiling:>5}: keeps {s['n_entity_values']:>6,} values, "
                f"client coverage {s['client_coverage']:.3f}"
            )

    out = paths.report_path("hub_band.json")
    paths.ensure_parent(out)
    out.write_text(json.dumps({"recipe": recipe, "entities": results}, indent=2) + "\n")
    print(f"\nwrote {out}")
    record_run(cfg, script="35_hub_band", metrics={"recipe": recipe})


if __name__ == "__main__":
    main()
