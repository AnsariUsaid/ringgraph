#!/usr/bin/env python
"""Verify the Neo4j instance is reachable and has what the pipeline needs.

Run this before any load. It checks the connection, the GDS version, and which
community-detection algorithms are actually available — plan.md §Part 3 asks for
Leiden's availability to be verified rather than assumed, since it has
historically been Enterprise-only.
"""

from __future__ import annotations

import json

from fds import paths
from fds.cli import base_parser
from fds.graphdb import server_report


def main() -> None:
    base_parser(__doc__.splitlines()[0]).parse_args()
    report = server_report()

    print("\n-- server --")
    for key, value in report.items():
        if key == "algorithms":
            continue
        print(f"  {key}: {value}")

    algorithms = report.get("algorithms")
    if isinstance(algorithms, list):
        print(f"\n-- community / centrality algorithms ({len(algorithms)} found) --")
        for name in algorithms:
            print(f"  {name}")
        has_leiden = any("leiden" in a for a in algorithms)
        print(f"\n  Leiden available: {has_leiden}  (Louvain is the fallback if not)")

    out = paths.report_path("neo4j_check.json")
    paths.ensure_parent(out)
    out.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
