#!/usr/bin/env python
"""Causal (deployable) setting: M1 against the graph model, per delay, with ablations.

  m1     the existing tabular model, untouched.
  ctrl   M1 + delayed-label history on tabular keys only (what a tabular team could add).
  graph  M1 + ctrl + everything relational: shared-entity exposure over many keys,
         label-free neighbourhood behaviour, two-hop propagation, ring breadth and
         recency, matured-label rates, causal client profile. The headline.
  rs / rl / rp / cp   (--ablations, delay-30 worker only) one relational family at a time.

At time t only rows before t and labels confirmed by t are used; the test period's
own earlier transactions and matured labels are included. Same per-seed randomness
for every model so differences are paired; every delay is reported; nothing is
selected on test. M1's scores are trained once and cached for reuse.
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
from fds.splits import Split

SEEDS = [11, 22, 33, 44, 55]
FPRS = {"tpr_at_fpr_1pct": 0.01, "tpr_at_fpr_0.1pct": 0.001}
HEADLINE = (("m1", "ctrl"), ("m1", "graph"), ("ctrl", "graph"))
ABLATION = (("m1", "rs"), ("m1", "rl"), ("m1", "rp"), ("m1", "cp"), ("ctrl", "rl"), ("ctrl", "rp"))
M1_CACHE = paths.DATA_ROOT / "m1_scores.npz"


def table_columns(path, prefixes: tuple[str, ...]) -> list[str]:
    return [c for c in pq.read_schema(path).names if c.startswith(prefixes)]


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, nargs="*", default=SEEDS)
    parser.add_argument("--delays", type=int, nargs="*", default=[30], help="empty = only train/cache M1")
    parser.add_argument("--ablations", action="store_true")
    parser.add_argument("--out", default="graph_sweep_tuned")
    parser.add_argument("--ctrl-config", default=str(paths.CONFIGS_DIR / "tuned" / "ctrl_d30.toml"))
    parser.add_argument("--graph-config", default=str(paths.CONFIGS_DIR / "tuned" / "graph_d30.toml"))
    args = parser.parse_args()
    cfg = resolve(args)
    recipe = cfg.uid.recipe_name
    ctrl_params = load_config(args.ctrl_config).model.params
    graph_params = load_config(args.graph_config).model.params

    base = load_base()
    m1_features = tabular_feature_columns(base)
    schema.assert_no_denied_features(m1_features)
    df = base
    wanted = {
        "labelfeat": (paths.labelfeat_path(recipe), tuple(p for d in args.delays for p in (f"lfc{d}_", f"lfg{d}_", f"lfa{d}_"))),
        "relfeat": (paths.relfeat_path(recipe), tuple(p for d in args.delays for p in (f"rl{d}_", f"rp{d}_")) + ("rs_",)),
        "profile": (paths.DATA_ROOT / "profile" / f"recipe={recipe}" / "profile.parquet", ("cp_",)),
    }
    for name, (path, prefixes) in wanted.items():
        if not args.delays:
            break
        cols = table_columns(path, prefixes)
        df = df.merge(read_parquet(path, columns=[schema.KEY, *cols]), on=schema.KEY, how="left", validate="one_to_one")
        print(f"  {name:<10}{len(cols):>5} columns", flush=True)
    print(f"M1: {len(m1_features):,} features  seeds {args.seeds}  delays {args.delays}", flush=True)

    frames = split_frames(df, [schema.KEY, schema.AMOUNT])
    test_idx, val_idx = frames[Split.TEST][0].index, frames[Split.VAL][0].index
    y = df.loc[test_idx, schema.TARGET].to_numpy()
    y_val = df.loc[val_idx, schema.TARGET].to_numpy()
    amount = df.loc[test_idx, schema.AMOUNT].to_numpy("float64")

    def train(features: list[str], label: str, params) -> tuple[np.ndarray, np.ndarray]:
        print(f"\n== training {label} ({len(features):,} features)", flush=True)
        runs = train_seed_sweep(
            split_frames(df, features), features=features, categorical=categorical_columns(df, features),
            params=params, num_boost_round=cfg.model.num_boost_round,
            early_stopping_rounds=cfg.model.early_stopping_rounds, seeds=args.seeds,
        )
        for seed, v, s, it in runs:
            print(f"   seed {seed}: iter {it}  val TPR@1% {evaluate(y_val, v)['tpr_at_fpr_1pct']:.4f}  test TPR@1% {evaluate(y, s)['tpr_at_fpr_1pct']:.4f}", flush=True)
        return np.stack([r[1] for r in runs]), np.stack([r[2] for r in runs])

    if M1_CACHE.exists():
        z = np.load(M1_CACHE)
        m1v, m1 = z["val"], z["test"]
        print(f"M1 scores reused from {M1_CACHE.name}", flush=True)
    else:
        m1v, m1 = train(m1_features, "M1", cfg.model.params)
        np.savez_compressed(M1_CACHE, val=m1v, test=m1)
    if not args.delays:
        return

    def cols(*prefixes: str) -> list[str]:
        return [c for c in df.columns if c.startswith(prefixes)]

    rng = np.random.default_rng(cfg.seed)
    report: dict = {"setting": "causal (deployable)", "seeds": args.seeds, "delays": {}}
    saved: dict[str, np.ndarray] = {"y_test": y, "y_val": y_val, "amount": amount}
    for d in args.delays:
        ctrl_cols = cols(f"lfc{d}_")
        graph_cols = cols(f"lfg{d}_", f"lfa{d}_", f"rl{d}_", f"rp{d}_", "rs_", "cp_")
        models = {"m1": (m1v, m1)}
        models["ctrl"] = train(m1_features + ctrl_cols, f"ctrl: tabular-key history, delay {d}d", ctrl_params)
        models["graph"] = train(m1_features + ctrl_cols + graph_cols, f"GRAPH: everything relational, delay {d}d", graph_params)
        if args.ablations:
            models["rs"] = train(m1_features + cols("rs_"), "rs: neighbourhood behaviour (label-free)", graph_params)
            models["rl"] = train(m1_features + cols(f"rl{d}_"), f"rl: multi-key delayed exposure, delay {d}d", graph_params)
            models["rp"] = train(m1_features + cols(f"rl{d}_", f"rp{d}_"), f"rp: rl + 2-hop propagation, delay {d}d", graph_params)
            models["cp"] = train(m1_features + cols("cp_"), "cp: causal client profile", graph_params)
        for name, (v, s) in models.items():
            saved[f"d{d}_{name}_val"], saved[f"d{d}_{name}_test"] = v, s

        t_df = df.loc[test_idx]
        strata = {
            "full_test": np.ones_like(y, dtype=bool),
            "new_client": t_df["rs_uid_gap_log"].isna().to_numpy(),  # no earlier txn from this client
            "linked": (t_df[f"rl{d}_max_rate_x"] > 0.10).to_numpy(),  # another client on a key looks fraudulent
        }
        pairs = tuple(p for p in HEADLINE + ABLATION if p[0] in models and p[1] in models)
        entry: dict = {"validation_tpr_1pct": {m: float(np.mean([evaluate(y_val, r)["tpr_at_fpr_1pct"] for r in v])) for m, (v, _) in models.items()}}
        light = len(args.seeds) < 5  # sensitivity delays: headline pairs on the full test set only
        for sname, mask in strata.items():
            if y[mask].sum() < 30 or (light and sname != "full_test"):
                continue
            block = {"n": int(mask.sum()), "n_fraud": int(y[mask].sum())}
            for mname, (_, s) in models.items():
                per_seed = [evaluate(y[mask], r[mask]) for r in s]
                for k in FPRS:
                    block[f"{mname}_{k}"] = [p[k] for p in per_seed]
            for k, fpr in FPRS.items():
                for a, b in (pairs if sname == "full_test" else HEADLINE):
                    block[f"{b}_minus_{a}_{k}"] = paired_bootstrap_difference(
                        y[mask], models[a][1].mean(0)[mask], models[b][1].mean(0)[mask], target_fpr=fpr, rng=rng, n_boot=300)
            if sname == "full_test":
                for mname, (_, s) in models.items():
                    dp = [dollars_and_precision(y, amount, r) for r in s]
                    block[f"{mname}_dollar_recall_1pct"] = [x["dollar_recall"] for x in dp]
                    block[f"{mname}_precision_1pct"] = [x["precision"] for x in dp]
                    block[f"{mname}_alerts_1pct"] = [x["alerts"] for x in dp]
                    block[f"{mname}_frauds_caught_1pct"] = [x["frauds_caught"] for x in dp]
            entry[sname] = block
        report["delays"][str(d)] = entry

        print(f"\n---- delay {d}d (test, mean over {len(args.seeds)} seeds; validation TPR@1%: " + ", ".join(f"{m} {v:.3f}" for m, v in entry["validation_tpr_1pct"].items()) + ") ----")
        for sname in strata:
            if sname not in entry:
                continue
            block = entry[sname]
            print(f" [{sname}] {block['n']:,} rows, {block['n_fraud']:,} fraud")
            for k in FPRS:
                print(f"   {k:<18} " + "   ".join(f"{m} {np.mean(block[f'{m}_{k}']):.4f}" for m in models))
                for a, b in HEADLINE:
                    r = block[f"{b}_minus_{a}_{k}"]
                    print(f"      {b}-{a}: {r['observed_difference']:+.4f}  95% CI [{r['ci_low']:+.4f}, {r['ci_high']:+.4f}]  excludes 0: {r['excludes_zero']}")
        out = paths.report_path(f"{args.out}_d{d}.json")
        paths.ensure_parent(out)
        out.write_text(json.dumps({**report, "delays": {str(d): entry}}, indent=2) + "\n")
        np.savez_compressed(paths.DATA_ROOT / f"{args.out}_d{d}_scores.npz", **saved)
        print(f"wrote {out}", flush=True)

    record_run(cfg, script="93_graph_sweep")


if __name__ == "__main__":
    main()
