#!/usr/bin/env python
"""Which attributes can carry a cross-client ring signal?

Trap A restricts the thesis to cross-client structure, which makes the choice of
linking entity the central empirical question of the graph model — not a design
preference. This script answers it directly: for each candidate attribute, does
it group fraud clients together beyond what its own subpopulation's fraud rate
would produce by chance?

Run before building the Neo4j graph. An attribute that scores at or below chance
here cannot support the thesis no matter how good its coverage looks.
"""

from __future__ import annotations

import json

from fds import paths, schema
from fds.artifacts import read_parquet
from fds.cli import base_parser, record_run, resolve
from fds.ingest import load_base
from fds.profiling import fraud_cooccurrence
from fds.rng import rng_for

CANDIDATES = [
    "card1",
    "card2",
    "addr1",
    "P_emaildomain",
    "R_emaildomain",
    "DeviceInfo",
    "id_31",
    "id_33",
]


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--recipe", default=None)
    parser.add_argument("--permutations", type=int, default=25)
    args = parser.parse_args()
    cfg = resolve(args)
    recipe = args.recipe or cfg.uid.recipe_name

    uid_map = read_parquet(paths.uid_map_path(recipe))
    df = load_base(columns=[schema.KEY, schema.TARGET, *CANDIDATES]).merge(
        uid_map, on=schema.KEY, validate="one_to_one"
    )
    # A client counts as fraud-positive if any of its transactions is.
    client_label = df.groupby(schema.UID, observed=True)[schema.TARGET].max()

    # The composite device fingerprint, evaluated as a candidate in its own right.
    df["DeviceFP"] = (
        df["DeviceInfo"].astype("string")
        + "|"
        + df["id_31"].astype("string")
        + "|"
        + df["id_33"].astype("string")
    )

    results = {}
    print(
        f"\n{'attribute':<16}{'groups':>8}{'sub_p':>8}{'>=3 obs':>9}{'null':>9}{'sd_away':>9}  verdict"
    )
    print("-" * 74)
    for column in [*CANDIDATES, "DeviceFP"]:
        if column not in df.columns:
            continue
        stats = fraud_cooccurrence(
            df[column],
            df[schema.UID],
            client_label,
            rng=rng_for(f"edge_signal_{column}", cfg.seed),
            max_clients=cfg.graph.hub_max_degree,
            min_clients=cfg.graph.hub_min_degree,
            n_permutations=args.permutations,
        )
        results[column] = stats
        if not stats.get("n_groups"):
            continue
        sd = stats["groups_ge_3_fraud_sd_away"]
        verdict = "USABLE" if sd >= 3 else ("disperses fraud" if sd <= -3 else "no signal")
        print(
            f"{column:<16}{stats['n_groups']:>8,}{stats['subpopulation_fraud_rate']:>8.4f}"
            f"{stats['groups_ge_3_fraud_observed']:>9,}"
            f"{stats['groups_ge_3_fraud_null_mean']:>9.1f}{sd:>9.1f}  {verdict}"
        )

    out = paths.report_path("edge_signal.json")
    paths.ensure_parent(out)
    out.write_text(json.dumps({"recipe": recipe, "attributes": results}, indent=2) + "\n")
    print(f"\nwrote {out}")
    record_run(cfg, script="45_edge_signal", metrics={"recipe": recipe})


if __name__ == "__main__":
    main()
