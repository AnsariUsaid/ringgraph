#!/usr/bin/env python
"""One table: normal (M1) vs control vs graph, per delay, plus the offline ladder.

Reads reports/graph_sweep_tuned_d*.json (causal) and reports/offline_ladder.json
(offline) and writes the small reports/headline.json the API and results page read.
Pure formatting: no model is trained here.
"""

from __future__ import annotations

import json

import numpy as np

from fds import paths

K1, K01 = "tpr_at_fpr_1pct", "tpr_at_fpr_0.1pct"


def mean_sd(values) -> dict[str, float]:
    return {"mean": float(np.mean(values)), "sd": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0}


def causal_block(entry: dict) -> dict:
    full = entry["full_test"]
    models = [m for m in ("m1", "ctrl", "graph", "rs", "rl", "rp", "cp") if f"{m}_{K1}" in full]
    out: dict = {"n_test": full["n"], "n_fraud": full["n_fraud"], "models": {}, "comparisons": {}, "strata": {}}
    for m in models:
        out["models"][m] = {
            "tpr_1pct": mean_sd(full[f"{m}_{K1}"]),
            "tpr_0.1pct": mean_sd(full[f"{m}_{K01}"]),
            "n_seeds": len(full[f"{m}_{K1}"]),
        }
        for key, name in (("dollar_recall_1pct", "dollar_recall_1pct"), ("precision_1pct", "precision_1pct"),
                          ("alerts_1pct", "alerts_1pct"), ("frauds_caught_1pct", "frauds_caught_1pct")):
            if f"{m}_{key}" in full:
                out["models"][m][name] = mean_sd(full[f"{m}_{key}"])
    for key, value in full.items():
        if "_minus_" in key:
            out["comparisons"][key] = {k: value[k] for k in ("observed_difference", "ci_low", "ci_high", "excludes_zero")}
    for sname in ("new_client", "linked"):
        if sname in entry:
            block = entry[sname]
            out["strata"][sname] = {"n": block["n"], "n_fraud": block["n_fraud"],
                                    **{m: float(np.mean(block[f"{m}_{K1}"])) for m in ("m1", "ctrl", "graph") if f"{m}_{K1}" in block}}
    out["validation_tpr_1pct"] = entry.get("validation_tpr_1pct", {})
    return out


def main() -> None:
    headline: dict = {"causal": {}, "offline": None}
    for path in sorted(paths.REPORTS_DIR.glob("graph_sweep_tuned_d*.json")):
        report = json.loads(path.read_text())
        for delay, entry in report["delays"].items():
            headline["causal"][delay] = causal_block(entry)
    offline = paths.report_path("offline_ladder.json")
    if offline.exists():
        report = json.loads(offline.read_text())
        headline["offline"] = {
            "delay_days": report["delay_days"],
            "smoothing": report["smoothing"],
            "levels": {lvl: {"tpr_1pct": mean_sd(v[K1]), "tpr_0.1pct": mean_sd(v[K01]), "pr_auc": mean_sd(v["pr_auc"]),
                             "dollar_recall_1pct": mean_sd(v["dollar_recall_1pct"]), "precision_1pct": mean_sd(v["precision_1pct"]),
                             "alerts_1pct": mean_sd(v["alerts_1pct"]), "frauds_caught_1pct": mean_sd(v["frauds_caught_1pct"])}
                       for lvl, v in report["levels"].items()},
            "comparisons": {k: {x: v[x] for x in ("observed_difference", "ci_low", "ci_high", "excludes_zero")}
                            for k, v in report["comparisons"].items()},
        }

    print("== CAUSAL (deployable): fraud caught at 1% / 0.1% false alarms, test, mean over seeds ==")
    print(f"{'delay':>6} {'seeds':>5} {'normal 1%':>10} {'control 1%':>11} {'graph 1%':>9} {'graph vs normal':>17} {'graph vs control':>18}   {'normal 0.1%':>11} {'graph 0.1%':>11}")
    for delay in sorted(headline["causal"], key=int):
        b = headline["causal"][delay]
        m, c = b["models"], b["comparisons"]
        g_m, g_c = c.get(f"graph_minus_m1_{K1}"), c.get(f"graph_minus_ctrl_{K1}")
        rel = m["graph"]["tpr_1pct"]["mean"] / m["m1"]["tpr_1pct"]["mean"] - 1
        sig = lambda x: "*" if x and x["excludes_zero"] else " "  # noqa: E731
        print(f"{delay:>5}d {m['graph']['n_seeds']:>5} {m['m1']['tpr_1pct']['mean']:>10.3f} {m['ctrl']['tpr_1pct']['mean']:>11.3f} {m['graph']['tpr_1pct']['mean']:>9.3f} "
              f"{g_m['observed_difference']:>+10.3f}{sig(g_m)} ({rel:+.0%}) {g_c['observed_difference']:>+13.3f}{sig(g_c)}   "
              f"{m['m1']['tpr_0.1pct']['mean']:>11.3f} {m['graph']['tpr_0.1pct']['mean']:>11.3f}")
    print("  * = 95% paired-bootstrap interval excludes zero")
    if headline["offline"]:
        o = headline["offline"]
        print(f"\n== OFFLINE (retrospective, whole-dataset label-free aggregates; delay {o['delay_days']}d; smoothing {o['smoothing']}) ==")
        print(f"{'level':>6} {'TPR@1%':>8} {'TPR@0.1%':>9} {'PR-AUC':>8} {'$ recall':>9} {'precision':>10} {'alerts':>7} {'caught':>7}")
        for lvl, v in o["levels"].items():
            print(f"{lvl:>6} {v['tpr_1pct']['mean']:>8.3f} {v['tpr_0.1pct']['mean']:>9.3f} {v['pr_auc']['mean']:>8.3f} {v['dollar_recall_1pct']['mean']:>9.3f} "
                  f"{v['precision_1pct']['mean']:>10.3f} {v['alerts_1pct']['mean']:>7.0f} {v['frauds_caught_1pct']['mean']:>7.0f}")
    out = paths.report_path("headline.json")
    out.write_text(json.dumps(headline, indent=2) + "\n")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
