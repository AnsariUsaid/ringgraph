# Log — decisions, numbers, problems (append only)

## 2026-10-07 baseline facts
- Data: IEEE-CIS, 590,540 txns, 3.5% fraud. Split: train d0-119, val d120-150, test d151-181.
- M1 tuned LightGBM, 431 features: test AUC 0.894, TPR@1%FPR 0.442, TPR@0.1%FPR 0.237.
- M2 (shape-only graph features), 5 seeds: full_test mean diff vs M1 = -0.006 (sd 0.013). Null.
- Graph: link attrs DeviceInfo,id_31,id_33,id_30,id_17,id_19,id_20,id_13; degree band 2-10, weight>=1.
  5,312 linked clients of 217,850 (2.4%); 550 rings (>=3 clients); 112 with >=2 fraud clients; 358 with none.
- Existing design forbids neighbour-label features (D-40). We now deliberately add them, time-respecting with a delay.
- Repo authors: Ansari Usaid (49 commits). User (Lohithnath) is a collaborator.
- Manifests record /Users/usaid/... paths: cosmetic, ignore.
- `.gitignore` ignores all `*.md` except README.md, so `guidelines/*.md` are NOT tracked unless a rule is added (ask user).

## Decisions
- 2026-10-07: do not strengthen M1 (user choice). Add a delayed-label control from tabular keys so the gain can be attributed to graph.
- 2026-10-07: GNN skipped for now.
- 2026-10-07: commits are one line, conventional format, user identity only.

## 2026-10-07 decisions
- Own-client delayed history is a tabular key, so it is in the control, not credited to the graph.
- Graph model = M1 + every relational family; headline fixed in advance, ablations reported alongside. Model choice never made on test.
- "linked" stratum redefined by cross-client rate > 0.10 (hub keys made the count-based one cover 99.8% of rows).
- Bootstrap trimmed (300 resamples, ablation pairs on full test only): it cost ~15 min per delay.

## 2026-10-07 later decisions and problems
- Two settings, reported separately: causal (deployable) and offline (Kaggle-style: whole-dataset label-free aggregates + client-mean smoothing; test labels never read).
- Offline smoothing blend (client vs component, alpha) is chosen on validation only.
- Parity: control and graph tuned with the identical search space, budget and objective as M1 (validation TPR@1%FPR); tuned once at 30d and reused at other delays; ablations reuse the graph parameters.
- Memory: 15.7 GB RAM is the limit, not CPU (20 threads). Per-delay lean processes load only the columns they need; M1 scores are cached in `data/m1_scores.npz` and reused. Run parallel jobs with OMP_NUM_THREADS split (8-10 each).
- Sensitivity delays 7/60/90 use 3 seeds to save time; 30d (headline) and 14d use 5.
- Problems met: nested heredoc/escape bugs when generating scripts via python (use the Write/Edit tools); `--config` is already defined by `base_parser` (do not re-add).
- Do not commit regenerated `reports/edge_signal.json`, `profile.json`, `synchrony.json` or `runs/index.jsonl` from pipeline reruns without checking the diff.
- Untracked scratch outputs: `reports/label_smoke.json`, `reports/graph_sweep.json` (untuned v1), `reports/percolation.json`.
