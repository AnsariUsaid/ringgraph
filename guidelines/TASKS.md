# Tasks

Legend: [x] done, [ ] todo, [~] running. Do in order unless stated.

## Phase 0 — Environment and data  (DONE)
- [x] kaggle.json, kaggle in `.venv`, Windows download fix, data in `data/raw`
- [x] Pipeline 10 -> 20 -> 30 -> 35 -> 40 -> 45 -> 48 -> 50 -> 80 (82 community skipped: slow, off the path)
- [x] M1 reproduced in sweeps: test TPR@1% ~0.42-0.45 across seeds (committed 0.442). M1 is NEVER changed.

## Phase 1 — Dynamic label knowledge  (DONE)
- [x] `label_features.py`, `relational_features.py`, `client_profile.py` + leakage tests (all pass: `pytest tests/test_*leakage* tests/test_client_profile.py tests/test_offline_features.py`)
- [x] Control (tabular keys) built and tuned (`configs/tuned/ctrl_d30.toml`)
- [x] Graph model tuned on validation with M1's search space (`configs/tuned/graph_d30.toml`, val 0.610 vs control 0.602)
- [x] Risk propagation tried: no validation gain, dropped (kept in repo as a documented negative result)

## Phase 2 — Evaluate and prove  (RUNNING; logs in %LOCALAPPDATA%\Temp)
- [~] Causal 30d + ablations (rs, rl, rp, cp): `w1_causal_d30.log` -> `reports/graph_sweep_tuned_d30.json` (REQUIRED)
- [x] Causal 14d (5 seeds): normal 0.426, control 0.584, graph 0.603 at 1%FPR; graph-control +0.023* -> `reports/graph_sweep_tuned_d14.json`
- [~] Causal 90d, 60d, 7d (3 seeds, light mode; low value, kept to report every delay): `w4_causal_d*.log`
- [x] Offline ladder L0..L4 -> `reports/offline_ladder.json` (L0 0.426 -> L3 0.556 at 1%FPR; mean-smoothing hurt)
- [~] Offline max-smoothing check (validation-chosen): `w5_smoothing.log` -> `reports/offline_smoothing.json`
- [x] `scripts/98_summary.py` prints the one table and writes `reports/headline.json` (rerun when jobs finish)
- [ ] State attribution honestly: own history (control) vs cross-client graph vs offline aggregates vs smoothing

## Phase 3 — Push the difference further (judge on validation only, never tune on test)
- [ ] If graph-vs-control is still small: retune the graph per delay (7/14), more matured/recent-window features
- [ ] Refit M1 and graph on train+val (more history) and report as a separate "refit" line
- [ ] Optional: GNN (HGT/RGCN) on GPU (RTX 3060 6GB), install torch in `.venv` only; judge on validation first
- [ ] Optional: SHAP on flagged payments for the demo

## Phase 4 — Show it
- [ ] Write `reports/headline.json` (small, committed) for the API/web: M1 / control / graph per delay + offline ladder
- [ ] API `/metrics/models` serves M1, control, graph, ladder; Results page: three-bar headline, delay selector, "what is control / graph" explainer
- [ ] README: update Status, Findings, Reproducing (scripts 83-87, 93, 94, 96) and the two settings
- [ ] Commit only small artefacts; `data/` stays ignored

## How to proceed after the runs finish (checklist for the next session)
1. `git status`; read `reports/graph_sweep_tuned_d30.json` and `reports/offline_ladder.json`.
2. Build the summary table (Phase 2). If a log shows a Traceback, fix it and rerun only that job.
3. Update `guidelines/PROGRESS.md` and `LOG.md` with the final numbers, commit, push only if the user says so that turn.
4. Then Phase 4 (headline.json, API, results page, README).
