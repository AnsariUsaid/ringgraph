#!/usr/bin/env python
"""Detect candidate rings: Leiden over the client-to-client projection.

Runs on the LINKED projection, never the raw bipartite graph — communities over
a transaction-entity graph are not interpretable as rings (plan.md §Part 3).

Checks the plan's own verification rule as it goes: if the largest community
holds more than half the clients, the graph has percolated and the result is
meaningless regardless of how good the modularity looks.
"""

from __future__ import annotations

import json

from fds import paths
from fds.cli import base_parser, record_run, resolve
from fds.communities import community_profile, leiden, project, write_communities

LARGEST_COMMUNITY_LIMIT = 0.5


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--gamma", type=float, default=1.0, help="Leiden resolution")
    parser.add_argument("--no-write", action="store_true", help="skip writing ids back to Neo4j")
    args = parser.parse_args()
    cfg = resolve(args)

    info = project(min_weight=cfg.graph.min_edge_weight)
    print(f"projected {info['nodes']:,} clients, {info['relationships']:,} relationships")

    assignments = leiden(gamma=args.gamma)
    profile = community_profile(assignments)
    print("\n-- communities --")
    for key, value in profile.items():
        print(f"  {key:<26} {value:,.4f}" if isinstance(value, float) else f"  {key:<26} {value:,}")

    share = profile["largest_community_share"]
    verdict = "ok" if share < LARGEST_COMMUNITY_LIMIT else "FAILS plan.md verification rule"
    print(f"\n  largest community holds {share:.1%} of clients -- {verdict}")

    if not args.no_write:
        written = write_communities(assignments)
        print(f"  wrote community ids to {written:,} Client nodes")

    out = paths.report_path("communities.json")
    paths.ensure_parent(out)
    out.write_text(
        json.dumps({"gamma": args.gamma, "projection": info, "profile": profile}, indent=2) + "\n"
    )
    print(f"\nwrote {out}")
    record_run(cfg, script="62_communities", metrics=profile)


if __name__ == "__main__":
    main()
