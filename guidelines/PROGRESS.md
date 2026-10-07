# Progress (append newest at the bottom)

## 2026-10-07 — Session 1
- Audited repo (see LOG.md). Tests pass. Raw data absent locally.
- Decided: keep M1 as is; main bet is delayed-label graph features (Phase 1).
- Created `guidelines/` (CLAUDE.md, TASKS.md, PROGRESS.md, LOG.md).
- User placed `kaggle.json`; next: Phase 0 download.

- `kaggle.json` confirmed at `C:\Users\lohit\.kaggle`; `kaggle` 2.2.4 and `lightgbm` 4.7.0 already in `.venv`; no xgboost/torch yet.
- Edited `scripts/00_download.py` to find `kaggle.exe` on Windows (uncommitted).
- Shell tools were blocked by a transient classifier outage, so the download has NOT run yet.

- User approved committing + pushing `guidelines/` (rule `!guidelines/*.md` added to `.gitignore`). Commit/push was blocked by the same outage; check `git status` and `git log origin/main..` first thing next session.

**Next step:** run `.venv\Scripts\python.exe scripts/00_download.py`, then `nvidia-smi`, then rest of Phase 0.

## 2026-10-07 — Session 2
- Committed the download fix and `guidelines/` locally (not pushed).
- GPU: RTX 3060 6GB, driver 581.57 (CUDA 13.0).
- `00_download.py` now runs but Kaggle returns **403**: competition rules not accepted on the account that owns `kaggle.json`.

**Next step (needs the user):** accept the rules at https://www.kaggle.com/c/ieee-fraud-detection (join competition), then re-run `PYTHONPATH=src .venv/Scripts/python.exe scripts/00_download.py`. Then pipeline 10 -> 80.

## 2026-10-07 � Session 2 (cont.)
- Data downloaded; pipeline 10-50 and 80 ran. 82 (community) skipped: slow and off the M3 path. M1 untouched.
- Built `src/fds/label_features.py` (v1: tabular-key control `lfc`, device graph `lfg`, aggregates `lfa`) and `src/fds/relational_features.py` (`rl` delayed exposure over 13 keys incl. crossings, all/cross-client, plus matured-rate; `rs` label-free neighbourhood behaviour; `rp` 2-hop propagation). Leakage tests: `tests/test_label_leakage.py`, `tests/test_relational_leakage.py` (8 pass).
- Untuned sweep (M1's params for everything), delay 30d, 5 seeds, test TPR@1%FPR: M1 0.4245, control 0.5294, graph 0.5324. graph-M1 +0.103 (CI excl. 0); graph-control +0.008 (n.s.). At 0.1%FPR: M1 0.233, control 0.286, graph 0.295; graph-control +0.035 (CI excl. 0). Label-free `rs` alone: +0.009 (null). New clients (no own history): nothing helps.
- Reading: most of the gain is delayed own-client history (a tabular key). Graph adds a small, real gain mainly at the strict 0.1% FPR. Untuned models stop at ~60-100 rounds, so graph/control are being tuned with M1's search space (`94_tune_graph.py`, validation only).

**Next step:** when `/tmp/tune.log` finishes, run `scripts/93_graph_sweep.py --config configs/tuned/m1.toml --ctrl-config configs/tuned/ctrl_d30.toml --graph-config configs/tuned/graph_d30.toml` (all delays), then write the result into README/results page.
