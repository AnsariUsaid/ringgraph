#!/usr/bin/env python
"""GATE: is the cross-client signal coordination, or just a rare attribute?

Builds the D-38 identity-block link graph, extracts connected components, and
asks whether clients inside a component transact in alignment with each other
beyond what their own individual burst patterns produce.

The decisive comparison is not against chance in the abstract but between
component types: candidate rings (components holding two or more fraud clients)
versus controls (components holding none). If candidates show synchrony and
controls do not, coordination is real. If both look alike, what we have found is
an attribute-risk effect — available to any tabular model — and the thesis needs
restating before a graph database is worth building.

This is a diagnostic over the full period, not a model input, so no temporal
split applies.
"""

from __future__ import annotations

import json

import pandas as pd

from fds import paths, schema
from fds.artifacts import read_parquet
from fds.cli import base_parser, record_run, resolve
from fds.ingest import load_base
from fds.links import (
    IDENTITY_LINK_COLUMNS,
    LinkParams,
    build_links,
    component_summary,
    connected_components,
    percolation_report,
)
from fds.rng import rng_for
from fds.synchrony import (
    build_groups,
    per_component_synchrony,
    stratified_comparison,
    synchrony_test,
)

WINDOWS = {"1h": 3600.0, "6h": 21600.0, "24h": 86400.0}


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--recipe", default=None)
    parser.add_argument("--max-degree", type=int, default=50)
    parser.add_argument("--min-weight", type=int, default=2)
    parser.add_argument("--permutations", type=int, default=40)
    args = parser.parse_args()
    cfg = resolve(args)
    recipe = args.recipe or cfg.uid.recipe_name

    uid_map = read_parquet(paths.uid_map_path(recipe))
    columns = [schema.KEY, schema.TARGET, schema.TIME_RAW, *IDENTITY_LINK_COLUMNS]
    df = load_base(columns=[c for c in columns]).merge(
        uid_map, on=schema.KEY, validate="one_to_one"
    )
    client_label = df.groupby(schema.UID, observed=True)[schema.TARGET].max()

    params = LinkParams(min_degree=2, max_degree=args.max_degree, min_weight=args.min_weight)
    print(f"building links: degree band 2-{params.max_degree}, min weight {params.min_weight}")
    edges = build_links(df, uid_column=schema.UID, params=params)
    members = connected_components(edges)
    perc = percolation_report(members)

    print(f"\n-- graph --\n  edges {len(edges):,}")
    for key, value in perc.items():
        print(f"  {key:<26} {value:,.4f}" if isinstance(value, float) else f"  {key:<26} {value:,}")

    summary = component_summary(members, client_label)
    big = summary[summary["n_clients"] >= 3]
    candidates = big[big["n_fraud_clients"] >= 2]["component"].tolist()
    controls = big[big["n_fraud_clients"] == 0]["component"].tolist()
    print(
        f"\n  components >=3 clients: {len(big):,}  "
        f"candidates (>=2 fraud): {len(candidates):,}  controls (0 fraud): {len(controls):,}"
    )

    timed = df[[schema.UID, schema.TIME_RAW]]
    span = float(timed[schema.TIME_RAW].max() - timed[schema.TIME_RAW].min())

    results: dict[str, dict] = {"percolation": perc, "windows": {}}
    print(
        f"\n{'window':<8}{'set':<12}{'groups':>8}{'txns':>9}{'observed':>10}{'null':>11}{'ratio':>8}{'z':>8}"
    )
    print("-" * 74)
    for label, delta in WINDOWS.items():
        entry = {}
        for name, comps in (("candidates", candidates), ("controls", controls)):
            groups = build_groups(
                timed, members, uid_column=schema.UID, time_column=schema.TIME_RAW, components=comps
            )
            stats = synchrony_test(
                groups,
                delta=delta,
                span=span,
                rng=rng_for(f"sync_{label}_{name}", cfg.seed),
                n_permutations=args.permutations,
            )
            entry[name] = stats
            if not stats.get("n_groups"):
                continue
            print(
                f"{label:<8}{name:<12}{stats['n_groups']:>8,}{stats['n_transactions']:>9,}"
                f"{stats['observed']:>10,}{stats['null_mean']:>11.1f}"
                f"{stats['ratio']:>8.2f}{stats['z']:>8.1f}"
            )
        results["windows"][label] = entry

    # The aggregate table above is confounded by size: candidates and controls
    # differ ~10x in transactions per component, and the null scales with the
    # square of that, so the aggregate ratios are not comparable. The stratified
    # table is the one that answers the question.
    print("\n-- size-stratified (1h window): the comparison that is actually valid --")
    per_component = per_component_synchrony(
        timed,
        members,
        uid_column=schema.UID,
        time_column=schema.TIME_RAW,
        delta=WINDOWS["1h"],
        span=span,
        rng=rng_for("sync_per_component", cfg.seed),
        n_permutations=args.permutations,
    )
    strata = stratified_comparison(per_component, summary)
    print(f"\n{'txn bin':<10}{'kind':<12}{'comps':>7}{'observed':>11}{'null':>10}{'ratio':>9}")
    print("-" * 59)
    for _, row in strata.iterrows():
        ratio = "-" if pd.isna(row["ratio"]) else f"{row['ratio']:.2f}"
        print(
            f"{row['size_bin']!s:<10}{row['kind']:<12}{row['n_components']:>7,}"
            f"{row['observed']:>11,.0f}{row['null_mean']:>10.1f}{ratio:>9}"
        )
    results["stratified"] = strata.to_dict("records")

    out = paths.report_path("synchrony.json")
    paths.ensure_parent(out)
    out.write_text(
        json.dumps({"recipe": recipe, "params": vars(params), **results}, indent=2, default=str)
        + "\n"
    )
    print(f"\nwrote {out}")
    record_run(cfg, script="50_synchrony", metrics={"recipe": recipe})


if __name__ == "__main__":
    main()
