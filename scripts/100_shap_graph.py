#!/usr/bin/env python
"""Why the graph model flags what M1 misses: TreeSHAP on one graph model (delay 30d).

One model, one seed, the already-tuned graph parameters; nothing is tuned or selected
here. LightGBM's own ``pred_contrib`` gives the SHAP values, so no new dependency.
Attribution is by feature family, on all flagged payments and on the frauds the graph
model catches at 1% FPR that M1 does not, plus a few example payments.
"""

from __future__ import annotations

import json

import numpy as np
import pyarrow.parquet as pq

from fds import paths, schema
from fds.artifacts import read_parquet
from fds.cli import base_parser, resolve
from fds.config import load_config
from fds.evaluation import evaluate
from fds.features import categorical_columns, split_frames, tabular_feature_columns
from fds.ingest import load_base
from fds.models import train_lightgbm
from fds.splits import Split

DELAY = 30
SEED = 11
FAMILIES = (
    ("lfc", "own history (tabular keys)"),
    ("lfg", "device-graph labels"),
    ("lfa", "label aggregates"),
    ("rl", "delayed exposure, many keys"),
    ("rp", "two-hop propagation"),
    ("rs", "neighbourhood behaviour"),
    ("cp", "client profile"),
)


def family(feature: str) -> str:
    for prefix, name in FAMILIES:
        if feature.startswith((f"{prefix}{DELAY}_", f"{prefix}_")):
            return name
    return "M1 tabular"


def main() -> None:
    parser = base_parser(__doc__.splitlines()[0])
    parser.add_argument("--graph-config", default=str(paths.CONFIGS_DIR / "tuned" / "graph_d30.toml"))
    parser.add_argument("--out", default="shap_graph_d30")
    args = parser.parse_args()
    cfg = resolve(args)
    recipe = cfg.uid.recipe_name
    params = load_config(args.graph_config).model.params
    d = DELAY

    df = load_base()
    m1_features = tabular_feature_columns(df)
    schema.assert_no_denied_features(m1_features)
    wanted = {
        paths.labelfeat_path(recipe): (f"lfc{d}_", f"lfg{d}_", f"lfa{d}_"),
        paths.relfeat_path(recipe): (f"rl{d}_", f"rp{d}_", "rs_"),
        paths.DATA_ROOT / "profile" / f"recipe={recipe}" / "profile.parquet": ("cp_",),
    }
    for path, prefixes in wanted.items():
        cols = [c for c in pq.read_schema(path).names if c.startswith(prefixes)]
        df = df.merge(read_parquet(path, columns=[schema.KEY, *cols]), on=schema.KEY, how="left", validate="one_to_one")
    features = m1_features + [c for c in df.columns if c.startswith((f"lfc{d}_", f"lfg{d}_", f"lfa{d}_", f"rl{d}_", f"rp{d}_", "rs_", "cp_"))]
    print(f"graph model: {len(features):,} features, seed {SEED}, delay {d}d", flush=True)

    frames = split_frames(df, features)
    model = train_lightgbm(
        frames, features=features, categorical=categorical_columns(df, features), params=params,
        num_boost_round=cfg.model.num_boost_round, early_stopping_rounds=cfg.model.early_stopping_rounds,
        master_seed=SEED, name="shap_graph",
    )
    X, y_series = frames[Split.TEST]
    y = y_series.to_numpy()
    score = model.predict(X)
    print(f"test TPR@1% {evaluate(y, score)['tpr_at_fpr_1pct']:.4f}  (sweep mean over 5 seeds was 0.560)", flush=True)

    def flagged(s: np.ndarray) -> np.ndarray:
        return s >= np.quantile(s[y == 0], 0.99)  # 1% of legitimate payments alarmed

    m1 = np.load(paths.DATA_ROOT / "m1_scores.npz")["test"][0]
    flag, flag_m1 = flagged(score), flagged(m1)
    extra = flag & (y == 1) & ~flag_m1  # frauds only the graph model catches
    print(f"flagged {flag.sum():,}; frauds caught {int((flag & (y == 1)).sum()):,}; "
          f"of which M1 misses {int(extra.sum()):,}", flush=True)

    rows = np.flatnonzero(flag)
    contrib = model.booster.predict(X.iloc[rows][features], num_iteration=model.best_iteration, pred_contrib=True)[:, :-1]
    names = np.array(features)
    fam = np.array([family(f) for f in features])
    is_extra = extra[rows]

    def by_family(mask: np.ndarray) -> dict[str, float]:
        mean_abs = np.abs(contrib[mask]).mean(axis=0)
        total = mean_abs.sum()
        return {n: float(mean_abs[fam == n].sum() / total) for n in sorted(set(fam), key=lambda n: -mean_abs[fam == n].sum())}

    def top(mask: np.ndarray, k: int = 15) -> list[dict]:
        mean_abs = np.abs(contrib[mask]).mean(axis=0)
        return [{"feature": names[i], "family": fam[i], "mean_abs_shap": float(mean_abs[i])} for i in np.argsort(-mean_abs)[:k]]

    examples = []
    for r in np.flatnonzero(is_extra)[:5]:
        order = np.argsort(-np.abs(contrib[r]))[:5]
        examples.append({
            "test_row": int(rows[r]), "score": float(score[rows[r]]), "m1_score": float(m1[rows[r]]),
            "top_features": [{"feature": names[i], "family": fam[i], "shap": float(contrib[r, i])} for i in order],
        })

    report = {
        "delay_days": d, "seed": SEED, "n_features": len(features),
        "test_tpr_at_1pct_fpr": evaluate(y, score)["tpr_at_fpr_1pct"],
        "flagged": int(flag.sum()), "frauds_caught": int((flag & (y == 1)).sum()), "caught_only_by_graph": int(extra.sum()),
        "family_share_all_flagged": by_family(np.ones(len(rows), dtype=bool)),
        "family_share_caught_only_by_graph": by_family(is_extra),
        "top_features_caught_only_by_graph": top(is_extra),
        "examples": examples,
    }
    out = paths.report_path(f"{args.out}.json")
    out.write_text(json.dumps(report, indent=2))
    print("\nshare of |SHAP| by family, frauds only the graph model catches:")
    for n, v in report["family_share_caught_only_by_graph"].items():
        print(f"  {n:<30}{v:6.1%}")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
