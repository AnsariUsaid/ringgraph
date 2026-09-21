#!/usr/bin/env python
"""The Trap A gate: how strongly do labels cluster on reconstructed client identity?

plan.md §Part 1 requires this before anything else is built. If clients are
near-pure, fraud is clustered on client identity by construction, and the thesis
must rest on *cross-client* structure — distinct reconstructed identities linked
by a shared device, address, card attribute or email — rather than on the
within-client structure the labelling rule already implies.

The observed purity is reported against a permutation null that holds prevalence
and the client size distribution fixed. Without that null the number is not
interpretable: at 3.5% prevalence a three-transaction client is all-legitimate
about 90% of the time by chance alone.
"""

from __future__ import annotations

import json

from fds import paths, schema
from fds.artifacts import read_parquet
from fds.cli import base_parser, record_run, resolve
from fds.entities import UID_RECIPES
from fds.ingest import load_base
from fds.profiling import homogeneity_null, label_homogeneity
from fds.rng import rng_for

MIN_SIZE = 2


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--recipes", nargs="*", default=sorted(UID_RECIPES))
    parser.add_argument("--permutations", type=int, default=20)
    args = parser.parse_args()
    cfg = resolve(args)

    base = load_base(columns=[schema.KEY, schema.TARGET])
    results = {}

    for name in args.recipes:
        path = paths.uid_map_path(name)
        if not path.exists():
            print(f"  {name}: no uid map — run scripts/30_uid_map.py first")
            continue

        uid_map = read_parquet(path)
        merged = base.merge(uid_map, on=schema.KEY, how="inner", validate="one_to_one")
        observed = label_homogeneity(merged[schema.UID], merged[schema.TARGET], min_size=MIN_SIZE)
        null = homogeneity_null(
            merged[schema.UID],
            merged[schema.TARGET],
            rng=rng_for(f"trap_a_{name}", cfg.seed),
            n_permutations=args.permutations,
            min_size=MIN_SIZE,
        )

        key = f"pure_share_size_ge_{MIN_SIZE}"
        excess = observed.get(key, float("nan")) - null.get(f"null_mean_{key}", float("nan"))
        results[name] = {"observed": observed, "null": null, "excess_purity": excess}

        print(f"\n-- {name} --")
        for label, value in observed.items():
            print(
                f"  {label:<38} {value:,.4f}"
                if isinstance(value, float)
                else f"  {label:<38} {value:,}"
            )
        if null:
            print(f"  {'null mean (random labels)':<38} {null[f'null_mean_{key}']:.4f}")
            print(f"  {'null std':<38} {null[f'null_std_{key}']:.4f}")
            print(f"  {'EXCESS PURITY over chance':<38} {excess:+.4f}")

    out = paths.report_path("label_homogeneity.json")
    paths.ensure_parent(out)
    out.write_text(json.dumps(results, indent=2) + "\n")
    print(f"\nwrote {out}")
    print(
        "\nReading this: a large positive excess purity confirms Trap A — labels are "
        "assigned per client, so within-client structure is baseline enrichment only "
        "and the thesis must rest on cross-client links."
    )
    record_run(
        cfg,
        script="40_label_homogeneity",
        metrics={k: v["excess_purity"] for k, v in results.items()},
    )


if __name__ == "__main__":
    main()
