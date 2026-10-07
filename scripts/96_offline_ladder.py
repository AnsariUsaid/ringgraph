#!/usr/bin/env python
"""Offline (retrospective) setting: a ladder from M1 up, then prediction smoothing.

Everything about the rows is on the table at once, future included; only test
LABELS are hidden. Delayed-label features still use only labels matured by each
row's time. Reported separately from the causal setting (93_graph_sweep.py).

  L0  M1, untouched.
  L1  + whole-dataset frequency and per-client aggregates (the winners' features).
  L2  + delayed own-client history (the control's label features).
  L3  + graph: shared-entity exposure, structure, propagation, component size.
  L4  L3 with each score blended with its client's / component's mean score over
      the rows being scored (the winners' post-processing). The blend weight and
      grouping are chosen on VALIDATION, never on test.
"""

from __future__ import annotations

import json

import numpy as np
import pyarrow.parquet as pq

from fds import paths, schema
from fds.artifacts import read_parquet
from fds.cli import base_parser, record_run, resolve
from fds.config import load_config
from fds.evaluation import dollars_and_precision, evaluate, paired_bootstrap_difference
from fds.features import categorical_columns, split_frames, tabular_feature_columns
from fds.ingest import load_base
from fds.models import train_seed_sweep
from fds.offline_features import AGG_PREFIX, FE_PREFIX, GRAPH_PREFIX, component_ids, smooth_scores
from fds.splits import Split

SEEDS = [11, 22, 33, 44, 55]
ALPHAS = (1.0, 0.75, 0.5, 0.25, 0.0)


def table_columns(path, prefixes: tuple[str, ...]) -> list[str]:
    return [c for c in pq.read_schema(path).names if c.startswith(prefixes)]


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, nargs="*", default=SEEDS)
    parser.add_argument("--delay", type=int, default=30)
    parser.add_argument("--config", default=str(paths.CONFIGS_DIR / "tuned" / "m1.toml"))
    parser.add_argument("--graph-config", default=str(paths.CONFIGS_DIR / "tuned" / "graph_d30.toml"))
    parser.add_argument("--out", default="offline_ladder")
    args = parser.parse_args()
    cfg = resolve(args)
    recipe, d = cfg.uid.recipe_name, args.delay
    graph_params = load_config(args.graph_config).model.params

    base = load_base()
    m1 = tabular_feature_columns(base)
    schema.assert_no_denied_features(m1)
    sources = {
        "labelfeat": (paths.labelfeat_path(recipe), (f"lfc{d}_", f"lfg{d}_", f"lfa{d}_")),
        "relfeat": (paths.relfeat_path(recipe), (f"rl{d}_", f"rp{d}_", "rs_")),
        "offline": (paths.DATA_ROOT / "offline" / f"recipe={recipe}" / "offline.parquet", (FE_PREFIX, AGG_PREFIX, GRAPH_PREFIX)),
        "profile": (paths.DATA_ROOT / "profile" / f"recipe={recipe}" / "profile.parquet", ("cp_",)),
    }
    df = base
    for name, (path, prefixes) in sources.items():
        if not path.exists():
            print(f"(skipping {name}: {path.name} not built)")
            continue
        cols = table_columns(path, prefixes)
        df = df.merge(read_parquet(path, columns=[schema.KEY, *cols]), on=schema.KEY, how="left", validate="one_to_one")
        print(f"  {name:<10}{len(cols):>5} columns", flush=True)

    def cols(*prefixes: str) -> list[str]:
        return [c for c in df.columns if c.startswith(prefixes)]

    l1 = m1 + cols(FE_PREFIX, AGG_PREFIX)
    l2 = l1 + cols(f"lfc{d}_")
    l3 = l2 + cols(GRAPH_PREFIX, f"lfg{d}_", f"lfa{d}_", f"rl{d}_", f"rp{d}_", "rs_", "cp_")
    ladder = {"L0": m1, "L1": l1, "L2": l2, "L3": l3}
    schema.assert_no_denied_features(l3)
    print({k: len(v) for k, v in ladder.items()}, flush=True)

    frames = split_frames(df, [schema.KEY, schema.AMOUNT])
    val_idx, test_idx = frames[Split.VAL][0].index, frames[Split.TEST][0].index
    y_val, y = (df.loc[i, schema.TARGET].to_numpy() for i in (val_idx, test_idx))
    amount = df.loc[test_idx, schema.AMOUNT].to_numpy("float64")
    groups = {"uid": None, "component": None}
    with_uid = df[[schema.KEY]].merge(read_parquet(paths.uid_map_path(recipe)), on=schema.KEY)
    groups["uid"] = with_uid[schema.UID].astype("category").cat.codes.to_numpy()
    groups["component"] = component_ids(load_base(columns=base_columns_for_components()).merge(read_parquet(paths.uid_map_path(recipe)), on=schema.KEY))

    scores: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for name, features in ladder.items():
        print(f"\n== training {name} ({len(features):,} features)", flush=True)
        params = None if name == "L0" else graph_params
        runs = train_seed_sweep(
            split_frames(df, features), features=features, categorical=categorical_columns(df, features),
            params=params or cfg.model.params, num_boost_round=cfg.model.num_boost_round,
            early_stopping_rounds=cfg.model.early_stopping_rounds, seeds=args.seeds,
        )
        scores[name] = (np.stack([r[1] for r in runs]), np.stack([r[2] for r in runs]))
        for seed, v, s, it in runs:
            print(f"   seed {seed}: iter {it}  val TPR@1% {evaluate(y_val, v)['tpr_at_fpr_1pct']:.4f}  test TPR@1% {evaluate(y, s)['tpr_at_fpr_1pct']:.4f}", flush=True)

    # L4: choose grouping and blend on validation, apply to test.
    val_g = {k: g[val_idx] for k, g in ((k, v) for k, v in groups.items())}
    test_g = {k: g[test_idx] for k, g in ((k, v) for k, v in groups.items())}
    v3, t3 = scores["L3"]
    best, best_val = ("uid", 1.0), -1.0
    print("\nchoosing the smoothing on validation (mean TPR@1% over seeds):")
    for gname in groups:
        for a in ALPHAS:
            v = np.mean([evaluate(y_val, smooth_scores(r, val_g[gname], a))["tpr_at_fpr_1pct"] for r in v3])
            print(f"   {gname:<10} alpha {a:<5} {v:.4f}")
            if v > best_val:
                best, best_val = (gname, a), v
    print(f"chosen on validation: group={best[0]} alpha={best[1]}", flush=True)
    scores["L4"] = (None, np.stack([smooth_scores(r, test_g[best[0]], best[1]) for r in t3]))

    rng = np.random.default_rng(cfg.seed)
    report: dict = {"setting": "offline (retrospective)", "delay_days": d, "smoothing": {"group": best[0], "alpha": best[1]}, "levels": {}, "comparisons": {}}
    print(f"\n==== offline ladder, delay {d}d, test, mean over {len(args.seeds)} seeds ====")
    print(f"{'level':<7}{'TPR@1%':>9}{'TPR@0.1%':>10}{'PR-AUC':>9}{'$ recall@1%':>13}{'precision@1%':>14}{'alerts':>8}")
    for name, (_, s) in scores.items():
        m = [evaluate(y, r) for r in s]
        dp = [dollars_and_precision(y, amount, r) for r in s]
        report["levels"][name] = {
            "tpr_at_fpr_1pct": [x["tpr_at_fpr_1pct"] for x in m],
            "tpr_at_fpr_0.1pct": [x["tpr_at_fpr_0.1pct"] for x in m],
            "pr_auc": [x["pr_auc"] for x in m],
            "dollar_recall_1pct": [x["dollar_recall"] for x in dp],
            "precision_1pct": [x["precision"] for x in dp],
            "alerts_1pct": [x["alerts"] for x in dp],
            "frauds_caught_1pct": [x["frauds_caught"] for x in dp],
        }
        print(f"{name:<7}{np.mean(report['levels'][name]['tpr_at_fpr_1pct']):>9.4f}{np.mean(report['levels'][name]['tpr_at_fpr_0.1pct']):>10.4f}"
              f"{np.mean([x['pr_auc'] for x in m]):>9.4f}{np.mean([x['dollar_recall'] for x in dp]):>13.4f}"
              f"{np.mean([x['precision'] for x in dp]):>14.4f}{np.mean([x['alerts'] for x in dp]):>8.0f}", flush=True)
    for a, b in (("L0", "L1"), ("L1", "L2"), ("L2", "L3"), ("L3", "L4"), ("L0", "L4")):
        for k, fpr in (("tpr_at_fpr_1pct", 0.01), ("tpr_at_fpr_0.1pct", 0.001)):
            r = paired_bootstrap_difference(y, scores[a][1].mean(0), scores[b][1].mean(0), target_fpr=fpr, rng=rng, n_boot=300)
            report["comparisons"][f"{b}_minus_{a}_{k}"] = r
            print(f"   {b}-{a} {k:<18} {r['observed_difference']:+.4f}  95% CI [{r['ci_low']:+.4f}, {r['ci_high']:+.4f}]  excludes 0: {r['excludes_zero']}")
    out = paths.report_path(f"{args.out}.json")
    paths.ensure_parent(out)
    out.write_text(json.dumps(report, indent=2) + "\n")
    np.savez_compressed(paths.DATA_ROOT / f"{args.out}_scores.npz", y_test=y, amount=amount, **{f"{k}_test": v[1] for k, v in scores.items()})
    print(f"\nwrote {out}")
    record_run(cfg, script="96_offline_ladder")


def base_columns_for_components() -> list[str]:
    return ["TransactionID", "DeviceInfo", "id_31", "id_33", "id_30"]


if __name__ == "__main__":
    main()
