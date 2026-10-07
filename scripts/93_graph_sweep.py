#!/usr/bin/env python
"""M1 against the graph model, with every ingredient ablated -- the headline experiment.

  m1    the existing tabular model, untouched.
  ctrl  M1 + delayed-label history on tabular keys only (what a tabular team could add).
  rs    M1 + label-free neighbourhood behaviour (new neighbours, bursts, gaps, amount z).
  rl    M1 + delayed-label exposure over many entity keys and crossings.
  rp    M1 + rl + two-hop propagation.
  graph M1 + everything relational (ctrl + v1 device graph + rl + rp + rs). The headline.

Same parameters (M1's tuned ones) for every model, shared per-seed randomness so
differences are paired. Every delay is reported. Nothing is selected on test: the
headline model is fixed in advance, ablations are reported alongside it.
"""

from __future__ import annotations

import json

import numpy as np

from fds import paths, schema
from fds.artifacts import read_parquet
from fds.config import load_config
from fds.cli import base_parser, record_run, resolve
from fds.evaluation import evaluate, paired_bootstrap_difference
from fds.features import categorical_columns, split_frames, tabular_feature_columns
from fds.ingest import load_base
from fds.label_features import AGG_PREFIX, CONTROL_PREFIX, DELAYS, GRAPH_PREFIX, label_feature_columns
from fds.models import train_seed_sweep
from fds.relational_features import LABEL_PREFIX, PROP_PREFIX, STRUCT_PREFIX
from fds.splits import Split

SEEDS = [11, 22, 33, 44, 55]
FPRS = {"tpr_at_fpr_1pct": 0.01, "tpr_at_fpr_0.1pct": 0.001}
VS = (("m1", "ctrl"), ("m1", "graph"), ("ctrl", "graph"), ("m1", "rs"), ("m1", "rl"), ("m1", "rp"))


def cols(df, prefix: str) -> list[str]:
    return [c for c in df.columns if c.startswith(prefix)]


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--seeds", type=int, nargs="*", default=SEEDS)
    parser.add_argument("--delays", type=int, nargs="*", default=list(DELAYS))
    parser.add_argument("--out", default="graph_sweep")
    parser.add_argument("--ctrl-config", default=None, help="tuned parameters for the control (default: M1's)")
    parser.add_argument("--graph-config", default=None, help="tuned parameters for the graph family (default: M1's)")
    args = parser.parse_args()
    cfg = resolve(args)
    recipe = cfg.uid.recipe_name

    base = load_base()
    m1_features = tabular_feature_columns(base)
    schema.assert_no_denied_features(m1_features)
    df = base.merge(read_parquet(paths.labelfeat_path(recipe)), on=schema.KEY, how="left", validate="one_to_one")
    df = df.merge(read_parquet(paths.relfeat_path(recipe)), on=schema.KEY, how="left", validate="one_to_one")
    del base
    print(f"M1: {len(m1_features):,} features  seeds {args.seeds}  delays {args.delays}", flush=True)

    frames = split_frames(df, [schema.KEY])
    test_idx, val_idx = frames[Split.TEST][0].index, frames[Split.VAL][0].index
    y = df.loc[test_idx, schema.TARGET].to_numpy()
    y_val = df.loc[val_idx, schema.TARGET].to_numpy()

    def train(features: list[str], label: str) -> tuple[np.ndarray, np.ndarray]:
        print(f"\n== training {label} ({len(features):,} features)", flush=True)
        runs = train_seed_sweep(
            split_frames(df, features),
            features=features,
            categorical=categorical_columns(df, features),
            params=params or cfg.model.params,
            num_boost_round=cfg.model.num_boost_round,
            early_stopping_rounds=cfg.model.early_stopping_rounds,
            seeds=args.seeds,
        )
        for seed, v, s, it in runs:
            print(
                f"   seed {seed}: iter {it}  val TPR@1% {evaluate(y_val, v)['tpr_at_fpr_1pct']:.4f}"
                f"  test TPR@1% {evaluate(y, s)['tpr_at_fpr_1pct']:.4f}",
                flush=True,
            )
        return np.stack([r[1] for r in runs]), np.stack([r[2] for r in runs])

    models_static = {"m1": train(m1_features, "M1")}
    models_static["rs"] = train(m1_features + cols(df, STRUCT_PREFIX), "rs: neighbourhood behaviour (label-free)", graph_params)
    rng = np.random.default_rng(cfg.seed)
    report: dict = {"seeds": args.seeds, "delays": {}}
    saved: dict[str, np.ndarray] = {"y_test": y, "y_val": y_val}

    for d in args.delays:
        ctrl_cols = label_feature_columns(df, d, CONTROL_PREFIX)
        v1_cols = label_feature_columns(df, d, AGG_PREFIX) + label_feature_columns(df, d, GRAPH_PREFIX)
        rl_cols = cols(df, f"{LABEL_PREFIX}{d}_")
        rp_cols = cols(df, f"{PROP_PREFIX}{d}_")
        rs_cols = cols(df, STRUCT_PREFIX)

        models = dict(models_static)
        models["ctrl"] = train(m1_features + ctrl_cols, f"ctrl: tabular-key history, delay {d}d", ctrl_params)
        models["rl"] = train(m1_features + rl_cols, f"rl: multi-key delayed exposure, delay {d}d", graph_params)
        models["rp"] = train(m1_features + rl_cols + rp_cols, f"rp: rl + 2-hop propagation, delay {d}d", graph_params)
        models["graph"] = train(
            m1_features + ctrl_cols + v1_cols + rl_cols + rp_cols + rs_cols, f"GRAPH: everything, delay {d}d", graph_params
        )
        for name, (v, s) in models.items():
            saved[f"d{d}_{name}_val"], saved[f"d{d}_{name}_test"] = v, s

        t_df = df.loc[test_idx]
        strata = {
            "full_test": np.ones_like(y, dtype=bool),
            "new_client": t_df["rs_uid_gap_log"].isna().to_numpy(),  # no earlier txn from this client
            "linked": (t_df[f"{LABEL_PREFIX}{d}_n_keys_conf_x"] > 0).to_numpy(),  # other client on a key has confirmed fraud
        }
        entry: dict = {"validation": {}}
        for name, (v, _) in models.items():
            entry["validation"][name] = float(np.mean([evaluate(y_val, r)["tpr_at_fpr_1pct"] for r in v]))
        for sname, mask in strata.items():
            if y[mask].sum() < 30:
                continue
            block = {"n": int(mask.sum()), "n_fraud": int(y[mask].sum())}
            for mname, (_, s) in models.items():
                per_seed = [evaluate(y[mask], r[mask]) for r in s]
                for k in FPRS:
                    block[f"{mname}_{k}"] = [p[k] for p in per_seed]
            for k, fpr in FPRS.items():
                for a, b in VS:
                    block[f"{b}_minus_{a}_{k}"] = paired_bootstrap_difference(
                        y[mask],
                        models[a][1].mean(0)[mask],
                        models[b][1].mean(0)[mask],
                        target_fpr=fpr,
                        rng=rng,
                        n_boot=500,
                    )
            entry[sname] = block
        report["delays"][str(d)] = entry

        print(f"\n---- delay {d}d  (test, mean over {len(args.seeds)} seeds; validation TPR@1%: "
              + ", ".join(f"{m} {v:.3f}" for m, v in entry["validation"].items()) + ") ----")
        for sname in strata:
            if sname not in entry:
                continue
            block = entry[sname]
            print(f" [{sname}] {block['n']:,} rows, {block['n_fraud']:,} fraud")
            for k in FPRS:
                print(f"   {k:<18} " + "   ".join(f"{m} {np.mean(block[f'{m}_{k}']):.4f}" for m in models))
                for a, b in VS[:3]:
                    r = block[f"{b}_minus_{a}_{k}"]
                    print(
                        f"      {b}-{a}: {r['observed_difference']:+.4f}  95% CI "
                        f"[{r['ci_low']:+.4f}, {r['ci_high']:+.4f}]  excludes 0: {r['excludes_zero']}"
                    )

        out = paths.report_path(f"{args.out}.json")
        paths.ensure_parent(out)
        out.write_text(json.dumps(report, indent=2) + "\n")  # rewritten per delay: partial results survive a crash
        np.savez_compressed(paths.DATA_ROOT / f"{args.out}_scores.npz", **saved)

    print(f"\nwrote {out}")
    record_run(cfg, script="93_graph_sweep")


if __name__ == "__main__":
    main()
