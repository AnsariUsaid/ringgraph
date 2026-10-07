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

## 2026-10-07 — Session 2 HAND-OFF (read this first in a fresh chat)

### Results in hand (test split, 5 seeds unless noted, paired bootstrap; `*` = 95% CI excludes 0)
Offline / retrospective ladder, delay 30d (`reports/offline_ladder.json`):

| level | TPR@1%FPR | TPR@0.1%FPR | $ recall@1% | precision@1% |
|---|---|---|---|---|
| L0 normal (M1) | 0.426 | 0.233 | 0.346 | 0.606 |
| L1 + whole-dataset client aggregates | 0.500* | 0.254 | 0.410 | 0.644 |
| L2 + own-client delayed history | 0.547* | 0.317* | 0.441 | 0.664 |
| L3 + graph features | 0.556* | 0.331 | 0.456 | 0.668 |
| L4 + client-mean smoothing | 0.556 | 0.331 | 0.456 | 0.668 |

L0->L3: +0.130 at 1% (+31% rel), +0.098 at 0.1% (+42% rel). Graph step alone (L3-L2): +0.012* at 1%, ~0 at 0.1%. Client-MEAN smoothing hurt on validation (0.652 -> 0.541 at alpha 0), so validation chose no smoothing. A max-smoothing variant is queued (see below).

Causal / deployable, delay 14d (`reports/graph_sweep_tuned_d14.json`): normal 0.426, control 0.584, graph 0.603 at 1%FPR. graph-normal +0.165* (+42% rel); graph-control +0.023* (the graph beats the tabular-key control significantly). At 0.1%FPR: normal 0.233, graph 0.336.

Causal 30d (untuned run earlier): normal 0.4245, control 0.529, graph 0.532 (+0.103*, +25% rel; graph-control +0.008 n.s.; at 0.1%FPR graph-control +0.035*). The TUNED 30d numbers with ablations are being produced (`reports/graph_sweep_tuned_d30.json`).

Honest attribution: most of the gain over normal is own-client delayed history (the control, a tabular key). Cross-client graph links add a smaller, significant gain (+0.023 at 14d, +0.012 offline). ~79% of fraud is first-time with no link to known fraud, so a massive graph-over-history gap is not available; do not claim one.

### Still running when this was written (21:50 IST) — logs in %LOCALAPPDATA%\Temp, tail with `Get-Content <log> -Wait -Tail 25`
- `w1_causal_d30.log`: realistic 30d + ablations (rs, rl, rp, cp) -> then `w4_causal_d90.log`, `w4_causal_d60.log` (3 seeds, light mode).
- `w5_smoothing.log`: offline L0+L3 with mean/max smoothing grid chosen on validation -> `reports/offline_smoothing.json`.
- then `w4_causal_d7.log` (3 seeds). ETA all done ~22:25.
If a log has no recent write and no python is running (check Task Manager / `Get-Process python`), the jobs died (PC crash or chat teardown). Restart only what is missing:
```
cd C:\Users\lohit\Desktop\RingGraph ; $env:PYTHONPATH="src"; $env:OMP_NUM_THREADS="10"
.venv\Scripts\python.exe -u scripts\93_graph_sweep.py --config configs\tuned\m1.toml --delays 30 --ablations > $env:TEMP\w1_causal_d30.log
.venv\Scripts\python.exe -u scripts\93_graph_sweep.py --config configs\tuned\m1.toml --delays 90 --seeds 11 22 33
.venv\Scripts\python.exe -u scripts\93_graph_sweep.py --config configs\tuned\m1.toml --delays 60 --seeds 11 22 33
.venv\Scripts\python.exe -u scripts\93_graph_sweep.py --config configs\tuned\m1.toml --delays 7 --seeds 11 22 33
.venv\Scripts\python.exe -u scripts\96_offline_ladder.py --config configs\tuned\m1.toml --levels L0 L3 --out offline_smoothing
```
(Run at most two at once: 15.7 GB RAM is the limit. M1 scores are cached in `data/m1_scores.npz`.)

### What to do next
1. When jobs finish: `PYTHONPATH=src .venv\Scripts\python.exe scripts\98_summary.py` (prints the table, writes `reports/headline.json`).
2. Put the final numbers in this file / README, commit, push only if the user says so that turn.
3. Phase 4: API `/metrics/models` + results page read `reports/headline.json`; README Status/Findings/Reproducing.
4. Optional (only if time and validation-justified): per-delay retune, refit on train+val, GNN.
