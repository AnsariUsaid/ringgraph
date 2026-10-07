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

## 2026-10-07 final-stretch notes
- PC crash (20 browser tabs) killed all background jobs ~21:30; code was intact (all committed). Restarted; the d30/d14 runs lost ~6 min of work. Stopped Phone Link and OneDrive sync to free ~0.3 GB (restart OneDrive from Start if wanted).
- Time/priority decision (user asked what is really needed): REQUIRED = causal 30d (+ablations) and the offline ladder; NICE = 14d and the max-smoothing check; LOW VALUE = 7/60/90d, kept only to honour "report every delay", trimmed to 3 seeds and full-test-only bootstrap ("light" mode when --seeds < 5). The bootstrap, not training, dominates runtime (10-15 min per delay).
- Offline finding: client-mean smoothing (the Kaggle winners' post-processing) does NOT help here; validation picks alpha=1.0. TPR@1%FPR is dominated by a few high scores that the mean dilutes. Max-smoothing is tested separately (`offline_smoothing.json`).
- Causal 14d: graph beats the control significantly (+0.023 at 1%FPR), larger than at 30d, because a shorter delay lets more confirmed fraud reach the features.
- Do not commit `reports/graph_sweep.json`, `label_smoke.json`, `percolation.json` (scratch / regenerated).

## 2026-10-07 22:00 offline max-smoothing result
- Validation picked group=uid, mode=max, alpha=0.75 (val 0.654 vs 0.652 unsmoothed). Test, 5 seeds: L0 0.426, L3 0.556, L4 0.557 at 1%FPR; L4-L3 -0.0006 (CI [-0.004,+0.004], n.s.), at 0.1%FPR -0.009 (n.s.). Smoothing, mean or max, does not help here. L3-L0 +0.115* at 1%, +0.091* at 0.1% (this L0/L3-only rerun; the full ladder file reports L0->L3 +0.130).

## 2026-10-07 22:00 causal 30d TUNED + ablations (reports/graph_sweep_tuned_d30.json, 5 seeds, test, * = CI excludes 0)
- TPR@1%FPR full test: M1 0.426, control 0.538, graph 0.560. graph-M1 +0.120*, ctrl-M1 +0.093*, graph-ctrl +0.027* (CI +0.018..+0.035). Validation: m1 0.497, ctrl 0.596, graph 0.611.
- TPR@0.1%FPR: M1 0.233, control 0.313, graph 0.310. graph-M1 +0.069*, but graph-ctrl -0.018 (n.s.). The untuned "graph helps at 0.1%" did NOT survive tuning: do not claim it.
- Ablations at 1%FPR (M1 + one family): rs 0.434 (label-free behaviour, ~null), rl 0.553, rp 0.552 (2-hop adds nothing over rl), cp 0.448 (client profile alone small). Nearly all of the lift is delayed exposure (rl), i.e. own-client history plus cross-key exposure.
- Strata: new_client (26.5k rows, 875 fraud): no model beats M1 significantly (graph-M1 +0.022 n.s.). linked (13.6k rows, 1,538 fraud): graph-M1 +0.047*, graph-ctrl +0.009 n.s. at 1%.
- Causal 7d done (3 seeds, light): graph-M1 -0.021 n.s. on its first stratum, see reports/graph_sweep_tuned_d7.json.
- Causal 90d (3 seeds, light, reports/graph_sweep_tuned_d90.json), TPR@1%FPR full test: M1 0.426, ctrl 0.472, graph 0.478. graph-M1 +0.041*, graph-ctrl +0.007 (n.s.). At 0.1%FPR nothing is significant. Longer delay = less confirmed fraud reaches the features, so the gain shrinks as expected.

## 2026-10-07 22:12 all jobs finished; final causal table (98_summary.py, test, TPR@1%FPR, * = CI excludes 0)
| delay | seeds | M1 | ctrl | graph | graph-M1 | graph-ctrl | 0.1%FPR M1 -> graph |
|---|---|---|---|---|---|---|---|
| 7d | 3 | 0.426 | 0.619 | 0.636 | +0.192* (+49%) | +0.016* | 0.233 -> 0.375 |
| 14d | 5 | 0.426 | 0.584 | 0.603 | +0.165* (+42%) | +0.023* | 0.233 -> 0.336 |
| 30d | 5 | 0.426 | 0.538 | 0.560 | +0.120* (+31%) | +0.027* | 0.233 -> 0.310 |
| 60d | 3 | 0.426 | 0.501 | 0.509 | +0.065* (+19%) | +0.005 | 0.233 -> 0.268 |
| 90d | 3 | 0.426 | 0.472 | 0.478 | +0.040* (+12%) | +0.007 | 0.233 -> 0.250 |
- Correction: relative lifts are graph/M1-1 (14d +42%, 30d +31%); the chat figures +39% / +28% were miscomputed.
- Graph beats control significantly at 7d/14d/30d (+0.016..+0.027), not at 60d/90d. Gain over M1 grows monotonically as the delay shrinks.
- Kaggle test_transaction/test_identity (unlabeled, later period) deliberately not downloaded: useless for causal setting and evaluation, at most a small offline L1 gain.

## 2026-10-07 ring fraud-rate check (scripts/99_ring_fraud_rate.py, no training; rings are label-free structure over the whole period)
- 550 rings, 4,762 clients (2.2% of clients), 30,785 txns (5.2% of all). Client fraud rate in rings 19.3% (917/4,762) vs ~3.7% base = ~5x. Transaction fraud rate in rings 9.1% vs 3.5% base = 2.6x. Rings hold 2,804 frauds, ~14% of all fraud txns.
- 192 rings have >=1 fraud client, 112 have >=2, 12 are all fraud, 358 have none. 837 of the 917 ring fraud clients sit in the 112 multi-fraud rings: the signal is concentrated.
- Ranking by structure only (composite, labels excluded): top 25 rings 32.5% fraud clients, top 50 24.5%, top 100 17.7%. Only the very top beats the all-ring average (19.3%), consistent with the size-controlled axes result.
- Rings are retrospective (built over the full period, not a causal detector). Fraud rate in ring transactions in the test period (day>=151): 8.9%.
- Safe wording: "the graph groups clients into candidate rings; clients in them are about 5x more likely to be fraudulent than the base rate". Not "we detect rings" as an evaluated detector, and 358 of 550 rings have no fraud.
