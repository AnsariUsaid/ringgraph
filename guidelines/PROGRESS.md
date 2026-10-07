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

## 2026-10-07 — Session 2 (end of session state)
Built and tested: delayed-label features (control + device graph), relational families (rl/rs/rp), matured-label rates, ring breadth + recency, causal client profile (winning-solution idea, past rows only), offline whole-dataset features + prediction smoothing. All leakage/brute-force tests pass.

Findings (validation/test as noted):
- Untuned, delay 30d, test TPR@1%FPR (5 seeds): M1 0.4245, control 0.5294, graph 0.5324. graph-M1 +0.103 (CI excl. 0); graph-control +0.008 (n.s.). At 0.1%FPR: M1 0.233, control 0.286, graph 0.295; graph-control +0.035 (CI excl. 0). New clients (no own history): nothing helps.
- Diagnostics (validation): own history covers ~21% of fraud under every identity definition tried (9 variants); of the 1,210 val fraud rows the control misses, almost none share a device with known fraud. So ~79% of fraud is first-time and unlinkable; no massive graph-over-history gap exists in key-sharing links.
- Risk propagation (rq): validation gain -0.003 (TPR@1%), dropped. Client profile (cp): +0.008 val TPR@1%, kept.
- Tuning with M1's search space: control val 0.602 (0.576 untuned), graph val 0.610.
- Kaggle winners (public write-ups): same UID (card1, addr1, day-D1), ~47 per-client aggregates over ALL rows incl. future, final prediction replaced by the client mean. The causal setting cannot use future rows, hence the separate offline setting.

Running at hand-off (logs in %LOCALAPPDATA%\Temp; `Get-Content <log> -Wait -Tail 25`):
`w1_causal_d30.log` (ablations), `w2_causal_d14.log`, `w3_offline.log`; queued: `w4_causal_d60/d7/d90.log` (3 seeds). Error found and fixed this session: duplicate `--config` in script 96 (the offline ladder had crashed at start).

**Next step:** wait for the jobs, build the single summary table, record numbers in LOG.md, then Phase 4 (headline.json, API, results page, README). Do NOT push unless the user says so that turn.
