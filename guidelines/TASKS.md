# Tasks

Legend: [x] done, [ ] todo, [~] in progress. Do in order unless stated.

## Phase 0 — Environment and data
- [x] Confirm `~/.kaggle/kaggle.json` exists; install `kaggle` in `.venv`
- [x] Fix `scripts/00_download.py` for Windows (`kaggle.exe` next to interpreter)
- [x] Download `train_transaction.csv`, `train_identity.csv` into `data/raw`
- [~] Check GPU (RTX 3060 6GB, CUDA 13 driver OK; trainer choice pending, nothing installed yet); decide GPU trainer (XGBoost `device="cuda"` or LightGBM GPU build) — inside `.venv` only
- [x] Run pipeline 10 -> 20 -> 30 -> 35 -> 40 -> 45 -> 48 -> 50 -> 80 (see README)
- [x] Reproduce M1 (smoke/sweep M1 ~0.42-0.45 across seeds; committed 0.442) (`configs/tuned/m1.toml`, `scripts/70_train_m1.py`); compare to `reports/m1_tuned_metrics.json` (test TPR@1% ~0.442)

## Phase 1 — Dynamic label knowledge (the main bet)
- [x] `src/fds/label_features.py`: for each transaction at time t and delay D, from clients linked at that time, count/share of neighbours with a fraud label confirmed <= t - D; also ring-level (community) confirmed-fraud count
- [x] `tests/test_label_leakage.py`: fails if any feature uses a label newer than t - D (mandatory)
- [x] `scripts/83_label_features.py`: build table for D in {30, 60, 90}
- [x] Control: same features from card1/addr1/email keys only (tabular target-encoding with delay)
- [~] Train M3 = M1 + structural + label features; 5 seeds. Built as `scripts/93_graph_sweep.py` (needs tuned params from `scripts/94_tune_graph.py`, running)

## Phase 2 — Better graph
- [ ] Weighted links: rare shared attribute counts more (IDF) instead of hard degree ceiling 10; target coverage well above 2.4% of clients, largest component < 50%
- [x] Multi-hop: 2-hop propagated suspicion (`rp` family in `src/fds/relational_features.py`)
- [ ] Re-run Phase 1 on the new graph

## Phase 3 — Evaluate and prove
- [ ] Paired bootstrap + 5 seeds: M1 vs M2 vs M3 vs control, at 1% and 0.1% FPR
- [ ] Strata: low-history clients, linked clients, rows with a confirmed-fraud neighbour
- [ ] Delay sweep table 30/60/90 and an amount-weighted (dollar) view
- [ ] Write `reports/*.json` the API/web can read

## Phase 4 — Show it
- [ ] API: `/metrics/models` serves M3 + control; optional `POST /score`
- [ ] Results page: M1 vs M3 headline, delay selector
- [ ] README: update Status, Findings, Reproducing

## Phase 5 — Optional (only if time)
- [ ] GNN (HGT/RGCN) on GPU, install torch into `.venv`
- [ ] SHAP explanations on flagged payments
