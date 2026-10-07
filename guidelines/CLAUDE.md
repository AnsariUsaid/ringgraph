# RingGraph — working guide (read this first, every session)

Then read `TASKS.md` (what to do next) and the tail of `PROGRESS.md` (where we stopped).

## Goal

Show, with a fair and defensible experiment, that **graph structure plus dynamic
knowledge (fraud the bank already knew about) catches fraud better than a plain
tabular model**. Tabular baseline strength is NOT a goal: the existing M1 stays
as it is, we do not spend time making it stronger.

Win condition: a graph-augmented model beats M1 on TPR @ 1% FPR (and 0.1%) on the
temporal test split, across 5 seeds, paired-bootstrap CI on the difference
excluding zero, with a leakage test proving no future label was used.

**Status (end of session 2):** achieved. Causal 14d: normal 0.426 -> graph 0.603 TPR@1%FPR
(+42% relative, graph beats the control by +0.023, significant). Causal 30d untuned: +0.103
(+25%). Offline ladder 30d: 0.426 -> 0.556 (+31%). Final tuned numbers:
`reports/graph_sweep_tuned_d*.json`, `reports/offline_ladder.json`, summary via
`scripts/98_summary.py`. READ `PROGRESS.md` (HAND-OFF section) first. Most of it is own-client delayed
history (the control); cross-client graph links add a small, significant gain mainly at
0.1% FPR. Never claim the whole gain is "graph": always show M1 / control / graph side by
side. Measured ceiling: ~79% of fraud is first-time fraud with no link to any known
fraud, so no key-sharing feature can give a massive gap over client history.

## Two settings (always reported separately)

1. **Causal / deployable** (`scripts/93_graph_sweep.py`): at time t only earlier rows and
   labels confirmed by t (fraud time + delay <= t). Earlier test-period transactions and
   matured test-period labels ARE usable. Delays 7/14/30/60/90 (30 is the realistic headline).
2. **Offline / retrospective, Kaggle-style** (`scripts/96_offline_ladder.py`): whole-dataset
   label-free aggregates (future rows' features included) plus per-client prediction
   averaging. Test LABELS are never used. Ladder: L0 M1, L1 +aggregates, L2 +own history,
   L3 +graph, L4 +smoothing (blend chosen on validation).

Words to use: **normal = M1** (one transaction at a time, untouched); **control** = M1 +
delayed history on tabular keys only (card1, addr1, email, uid); **graph** = control +
shared-entity exposure, ring breadth/recency, neighbourhood behaviour, two-hop propagation,
causal client profile. Risk propagation (`rq`) was tested and dropped (no validation gain).

## The idea in one paragraph

Clients (reconstructed from card1/addr1/D1n) are joined when they share a device
or browser attribute. Fraud rings reuse devices. If a linked client was *confirmed*
fraud at least `D` days before this transaction (chargeback delay), that is real
knowledge the bank had. Features built from it (plus weighted/multi-hop links) are
the "dynamic factors" M1 cannot see.

## Fairness (non-negotiable, this is what makes the claim survive questions)

- Temporal split is fixed in `fds/splits.py`. Never move it.
- A label may enter a feature for a transaction at time `t` only if it was confirmed
  at or before `t - delay`. A test must fail if this is violated.
- Report every delay (30/60/90 days), not only the best one.
- Include one control: M1 + delayed label features from the *tabular* keys
  (card1, addr1, email) only. Graph must beat M1 on its own; the control shows how
  much of the gain is truly graph. Cheap, do it, report it.
- Multi-seed (5) + paired bootstrap, as in `scripts/91_multiseed.py`.
- Report nulls honestly. Do not tune on the test split.

## Rules from the user

- **Never `git push`** unless the user says so in the current turn. (Session 2: the user
  asked to commit locally after decent progress, and to commit and push after fixing each
  detail.)
- **Commit only when asked or when the user has said to keep committing; ask before any
  deletion.** Do not commit regenerated `reports/*.json` or `runs/index.jsonl` by accident.
- Commit message: ONE line, conventional format `type(scope): summary`
  (`feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`). No body, no trailer,
  no co-author. Author is the user's configured git identity only.
- **venv only.** Use `.venv\Scripts\python.exe -m pip ...`. Never install globally.
- **Keep the file structure.** New code goes in the existing places:
  `src/fds/` (library), `scripts/NN_name.py` (numbered entrypoints),
  `tests/`, `api/`, `web/`, `configs/`. Pick the next free script number.
- Windows + PowerShell/Git Bash. Paths in docs use forward slashes.

## Style (ponytail)

Laziest thing that works. Reuse `fds` helpers before writing new ones (`links.py`,
`snapshots.py`, `evaluation.py`, `models.py`, `artifacts.py`, `config.py`).
No new abstractions, no config for constants that never change, stdlib/pandas first.
One small test per non-trivial rule (the leakage rule above is mandatory).

## Map of the repo

| Path | Role |
|---|---|
| `src/fds/entities.py` | client (uid) reconstruction |
| `src/fds/links.py` | attribute-sharing edges between clients |
| `src/fds/snapshots.py` | expanding-window snapshots, Trap B guard |
| `src/fds/structural.py`, `community_features.py` | existing graph features (M2) |
| `src/fds/models.py`, `evaluation.py`, `tuning.py` | training, metrics (incl. dollar recall and precision), tuning |
| `src/fds/label_features.py` | delayed-label features: control `lfc`, device graph `lfg`, aggregates `lfa`; DELAYS 7/14/30/60/90 |
| `src/fds/relational_features.py` | `rl` delayed exposure (13 keys, all/cross-client, matured rates, ring breadth, recency), `rs` label-free behaviour, `rp` 2-hop |
| `src/fds/client_profile.py` | `cp` causal client profile (winners' aggregates, past rows only) |
| `src/fds/offline_features.py` | `of_fe/of_agg/of_g` whole-dataset label-free features and `smooth_scores` |
| `src/fds/risk_propagation.py` | `rq` stage-1 score propagation (tested, no gain, not used) |
| `scripts/00..97_*.py` | pipeline, run in numeric order (see README) |
| `scripts/83` `84` `86` `87` | build the label / relational / profile / offline feature tables |
| `scripts/93_graph_sweep.py` | causal headline sweep (`--delays`, `--ablations`; caches M1 scores) |
| `scripts/94_tune_graph.py` | tune control / graph with M1's search space, validation only |
| `scripts/96_offline_ladder.py` | offline ladder with validation-chosen smoothing |
| `scripts/85`, `92` | risk-propagation check (negative result), v1 smoke sweep (superseded by 93) |
| `data/rings`, `reports/*.json`, `preds/model=m1_tuned` | committed demo artefacts |
| `api/main.py`, `web/` | demo backend and frontend |

## Session protocol

1. Read this file, `TASKS.md`, tail of `PROGRESS.md`.
2. Do the next unchecked task. Keep changes small.
3. Update `TASKS.md` (tick), append to `PROGRESS.md` (state + next step) and
   `LOG.md` (decisions, numbers, commands, problems). Do this before ending.
