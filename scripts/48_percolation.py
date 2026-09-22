#!/usr/bin/env python
"""Choose the link parameters by measuring percolation, not by guessing.

plan.md's verification rule requires the largest component to hold a sane share
of nodes (<50%). Degree banding alone does not deliver that: it caps how many
clients a single attribute value may link, but transitive linkage across
attributes fuses those groups anyway. Measured at a ceiling of 100 with no
weight floor, the largest component holds 94% of linked clients — the exact
failure mode the plan warns about.

The second control is a minimum edge weight: how many distinct identity
attributes two clients must share before they are linked at all. This script
sweeps both and reports the resulting component structure so the choice is a
reported parameter with evidence behind it.
"""

from __future__ import annotations

import json

from fds import paths, schema
from fds.artifacts import read_parquet
from fds.cli import base_parser, record_run, resolve
from fds.ingest import load_base
from fds.links import (
    IDENTITY_LINK_COLUMNS,
    LinkParams,
    build_links,
    connected_components,
    percolation_report,
)

CEILINGS = (10, 20, 50, 100)
WEIGHTS = (1, 2, 3)


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--recipe", default=None)
    args = parser.parse_args()
    cfg = resolve(args)
    recipe = args.recipe or cfg.uid.recipe_name

    uid_map = read_parquet(paths.uid_map_path(recipe))
    df = load_base(columns=[schema.KEY, *IDENTITY_LINK_COLUMNS]).merge(
        uid_map, on=schema.KEY, validate="one_to_one"
    )

    results = {}
    print(
        f"\n{'ceiling':>8}{'min_wt':>8}{'edges':>12}{'linked':>10}{'largest%':>10}{'comps>=3':>10}  rule"
    )
    print("-" * 68)
    for ceiling in CEILINGS:
        for weight in WEIGHTS:
            edges = build_links(df, schema.UID, params=LinkParams(2, ceiling, weight))
            members = connected_components(edges)
            report = percolation_report(members)
            results[f"{ceiling}_{weight}"] = {"ceiling": ceiling, "min_weight": weight, **report}
            if not report.get("n_components"):
                continue
            share = report["largest_component_share"]
            verdict = "ok" if share < 0.5 else "FAILS <50% rule"
            print(
                f"{ceiling:>8}{weight:>8}{len(edges):>12,}{report['n_linked_clients']:>10,}"
                f"{share * 100:>9.1f}%{report['n_components_ge_3']:>10,}  {verdict}"
            )

    out = paths.report_path("percolation.json")
    paths.ensure_parent(out)
    out.write_text(json.dumps({"recipe": recipe, "sweep": results}, indent=2) + "\n")
    print(f"\nwrote {out}")
    record_run(cfg, script="48_percolation", metrics={"recipe": recipe})


if __name__ == "__main__":
    main()
