#!/usr/bin/env python
"""Do the structural conclusions survive a different client-reconstruction rule?

plan.md's Verification section: "structural conclusions hold under both uid
variants, or the divergence is reported". This is the objection an examiner is
most likely to press, because reconstructed client identity is the project's
largest assumption -- if the rings are an artefact of how clients were defined,
nothing else stands.

Runs the full structural pipeline for each recipe and compares:

* **link graph shape** -- linked clients, components, percolation
* **ring inventory** -- how many rings, how many fraud-bearing
* **detector power** -- does ranking by composite still enrich for fraud
* **Trap A** -- does the labelling artefact reproduce

The recipes differ in strictness, so absolute counts *must* move: v3 splits
clients that v1 merges, giving more and smaller clients. What has to hold is
the *direction and shape* of the conclusions, not the raw numbers.
"""

from __future__ import annotations

import json

import pandas as pd

from fds import paths, schema
from fds.cli import base_parser, record_run, resolve
from fds.entities import UID_RECIPES
from fds.ingest import load_base
from fds.links import LinkParams, build_links, connected_components, percolation_report
from fds.profiling import homogeneity_null, label_homogeneity
from fds.rings import detect_rings, score_rings
from fds.rng import rng_for

MIN_SIZE = 2


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--recipes", nargs="*", default=sorted(UID_RECIPES))
    parser.add_argument("--permutations", type=int, default=15)
    args = parser.parse_args()
    cfg = resolve(args)
    link_columns = tuple(cfg.graph.link_types)
    params = LinkParams(
        min_degree=cfg.graph.hub_min_degree,
        max_degree=cfg.graph.hub_max_degree,
        min_weight=cfg.graph.min_edge_weight,
    )

    base = load_base(
        columns=[
            schema.KEY,
            schema.DAY,
            schema.TIME_RAW,
            schema.AMOUNT,
            schema.TARGET,
            *link_columns,
        ]
    )

    results = {}
    for recipe in args.recipes:
        uid_path = paths.uid_map_path(recipe)
        if not uid_path.exists():
            print(f"  {recipe}: no uid map, skipping")
            continue
        df = base.merge(pd.read_parquet(uid_path), on=schema.KEY, validate="one_to_one")
        print(f"\n=== {recipe} ===")

        edges = build_links(df, schema.UID, columns=link_columns, params=params)
        members = connected_components(edges)
        perc = percolation_report(members)

        membership, graph = detect_rings(df, link_columns=link_columns, params=params)
        rings = score_rings(
            membership,
            graph,
            df,
            rng=rng_for(f"sens_{recipe}", cfg.seed),
            attribute_columns=link_columns,
            n_permutations=10,
        )

        # Size-controlled enrichment, not precision@50 over base rate. The
        # latter is dominated by ring size and rose under shuffled labels; it
        # was retired in D-47 and this script was written before that.
        def enrichment(by: str, frame: pd.DataFrame = rings) -> float:
            if frame.empty:
                return float("nan")
            rate = float(frame["n_fraud_clients"].sum() / frame["n_clients"].sum())
            top = frame.sort_values(by, ascending=False, kind="stable").head(50)
            expected = float(top["n_clients"].sum()) * rate
            return float(top["n_fraud_clients"].sum() / expected) if expected else float("nan")

        fraudy = rings["n_fraud_clients"] >= 2
        baseline = float(fraudy.mean()) if len(rings) else float("nan")
        client_rate = float(rings["n_fraud_clients"].sum() / rings["n_clients"].sum())
        # Ranking by size is carried almost entirely by a handful of very large
        # rings, so report it with those excluded as well -- that is what
        # separates a size gradient from a few outliers.
        small = rings[rings["n_clients"] <= 15]

        homogeneity = label_homogeneity(df[schema.UID], df[schema.TARGET], min_size=MIN_SIZE)
        null = homogeneity_null(
            df[schema.UID],
            df[schema.TARGET],
            rng=rng_for(f"sens_null_{recipe}", cfg.seed),
            n_permutations=args.permutations,
            min_size=MIN_SIZE,
        )
        key = f"pure_share_size_ge_{MIN_SIZE}"
        excess = homogeneity[key] - null[f"null_mean_{key}"]

        entry = {
            "n_clients": int(df[schema.UID].nunique()),
            "n_linked_clients": perc.get("n_linked_clients", 0),
            "n_components": perc.get("n_components", 0),
            "largest_component_share": perc.get("largest_component_share", float("nan")),
            "n_rings": len(rings),
            "n_fraud_rings": int(fraudy.sum()),
            "ring_fraud_baseline": baseline,
            "client_fraud_rate": client_rate,
            "enrichment_burst": enrichment("burst_share"),
            "enrichment_burst_small_rings": enrichment("burst_share", small),
            "enrichment_size": enrichment("n_clients"),
            "enrichment_size_small_rings": enrichment("n_clients", small),
            "enrichment_composite": enrichment("composite"),
            "trap_a_excess_purity": excess,
        }
        results[recipe] = entry
        for label, value in entry.items():
            print(
                f"  {label:<28} {value:,.4f}"
                if isinstance(value, float)
                else f"  {label:<28} {value:,}"
            )

    print(f"\n{'metric':<28}" + "".join(f"{r.split('_')[0]:>14}" for r in results))
    print("-" * (28 + 14 * len(results)))
    for metric in (
        "n_clients",
        "n_linked_clients",
        "largest_component_share",
        "n_rings",
        "ring_fraud_baseline",
        "enrichment_burst",
        "enrichment_burst_small_rings",
        "enrichment_size",
        "enrichment_size_small_rings",
        "trap_a_excess_purity",
    ):
        row = f"{metric:<28}"
        for recipe in results:
            value = results[recipe][metric]
            row += f"{value:>14,.3f}" if isinstance(value, float) else f"{value:>14,}"
        print(row)

    out = paths.report_path("uid_sensitivity.json")
    paths.ensure_parent(out)
    out.write_text(json.dumps(results, indent=2) + "\n")
    print(f"\nwrote {out}")
    record_run(
        cfg,
        script="96_uid_sensitivity",
        metrics={r: v["enrichment_burst"] for r, v in results.items()},
    )


if __name__ == "__main__":
    main()
