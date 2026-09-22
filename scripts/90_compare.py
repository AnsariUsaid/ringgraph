#!/usr/bin/env python
"""The headline comparison: does structure add lift over the tuned baseline?

Reads prediction tables rather than models, so every metric here is a pure
function of [TransactionID, split, y_true, y_score] and the two models are
aligned by construction (D-11).

Three things the plan requires and one it does not:

* TPR at fixed FPR, not ROC-AUC, because "at the same false positive cost" is
  the question being asked.
* A bootstrap confidence interval on the *difference*, paired -- the same
  resample indices applied to both models (D-17). Two separate point estimates
  are not a finding.
* McNemar on the discordant pairs at the operating threshold.

And the addition: the comparison is reported **stratified**. Structural features
are non-trivial on roughly 1% of transactions, so a real effect is diluted
roughly 40:1 on the full test set and would vanish inside its own confidence
interval. Reporting only the full-set number would hide a true effect; reporting
only the subpopulation number would overstate its reach. Both are reported, with
the subpopulation size stated alongside.
"""

from __future__ import annotations

import json

import pandas as pd

from fds import paths, schema
from fds.artifacts import read_parquet
from fds.cli import base_parser, record_run, resolve
from fds.evaluation import (
    evaluate,
    mcnemar,
    paired_bootstrap_difference,
    tpr_at_fpr,
)
from fds.rng import rng_for

TARGET_FPR = 0.01


def latest_predictions(model: str) -> pd.DataFrame:
    candidates = sorted((paths.PREDS_DIR / f"model={model}").glob("run=*/preds.parquet"))
    if not candidates:
        raise SystemExit(f"no predictions found for model {model!r}")
    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    print(f"  {model:<12} {newest.parent.name}")
    return read_parquet(newest)


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--baseline", default="m1_tuned")
    parser.add_argument("--candidate", default="m2_c10w1")
    parser.add_argument("--attach-ceiling", type=int, default=10)
    parser.add_argument("--attach-weight", type=int, default=1)
    parser.add_argument("--cadence", type=int, default=7)
    parser.add_argument("--n-boot", type=int, default=1000)
    args = parser.parse_args()
    cfg = resolve(args)

    print("prediction tables:")
    base_preds = latest_predictions(args.baseline)
    cand_preds = latest_predictions(args.candidate)

    merged = base_preds.merge(
        cand_preds[[schema.KEY, "y_score"]], on=schema.KEY, suffixes=("_base", "_cand")
    )
    test = merged[merged["split"] == "test"].reset_index(drop=True)
    print(f"\ntest rows compared: {len(test):,}  fraud: {int(test['y_true'].sum()):,}")

    attach = read_parquet(
        paths.attach_path(cfg.uid.recipe_name, 2, args.attach_ceiling, args.cadence),
        columns=[schema.KEY, "has_structure", "st_degree"],
    )
    test = test.merge(attach, on=schema.KEY, how="left")
    test["has_structure"] = test["has_structure"].fillna(False)
    test["linked"] = test["st_degree"].fillna(0) > 0

    strata = {
        "full_test": test,
        "has_snapshot": test[test["has_structure"]],
        "linked_clients": test[test["linked"]],
    }

    results = {}
    print(
        f"\n{'stratum':<18}{'rows':>9}{'fraud':>7}{'base':>9}{'cand':>9}{'diff':>9}{'95% CI':>20}"
    )
    print("-" * 81)
    for name, block in strata.items():
        if block["y_true"].nunique() < 2 or len(block) < 50:
            print(f"{name:<18}{len(block):>9,}  too small to evaluate")
            continue
        y = block["y_true"].to_numpy()
        a = block["y_score_base"].to_numpy()
        b = block["y_score_cand"].to_numpy()

        base_m = evaluate(y, a)
        cand_m = evaluate(y, b)
        diff = paired_bootstrap_difference(
            y,
            a,
            b,
            target_fpr=TARGET_FPR,
            rng=rng_for(f"boot_{name}", cfg.seed),
            n_boot=args.n_boot,
        )
        threshold = tpr_at_fpr(y, a, TARGET_FPR)["threshold"]
        test_mcnemar = mcnemar(y, (a >= threshold).astype(int), (b >= threshold).astype(int))

        results[name] = {
            "n": len(block),
            "n_fraud": int(y.sum()),
            "baseline": base_m,
            "candidate": cand_m,
            "difference": diff,
            "mcnemar": test_mcnemar,
        }
        ci = f"[{diff['ci_low']:+.4f}, {diff['ci_high']:+.4f}]"
        print(
            f"{name:<18}{len(block):>9,}{int(y.sum()):>7,}"
            f"{base_m['tpr_at_fpr_1pct']:>9.4f}{cand_m['tpr_at_fpr_1pct']:>9.4f}"
            f"{diff['observed_difference']:>+9.4f}{ci:>20}"
        )

    print("\n-- verdict --")
    for name, r in results.items():
        d = r["difference"]
        verdict = "significant" if d["excludes_zero"] else "not distinguishable from zero"
        print(
            f"  {name:<18} {d['observed_difference']:+.4f}  {verdict}"
            f"  (McNemar p={r['mcnemar']['p_value']:.3g})"
        )

    out = paths.report_path(f"compare_{args.baseline}_vs_{args.candidate}.json")
    paths.ensure_parent(out)
    out.write_text(
        json.dumps(
            {
                "baseline": args.baseline,
                "candidate": args.candidate,
                "target_fpr": TARGET_FPR,
                "n_boot": args.n_boot,
                "strata": results,
            },
            indent=2,
            default=str,
        )
        + "\n"
    )
    print(f"\nwrote {out}")
    record_run(cfg, script="90_compare", metrics={k: v["difference"] for k, v in results.items()})


if __name__ == "__main__":
    main()
