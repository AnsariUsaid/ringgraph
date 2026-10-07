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

- **Never `git push`** unless the user says so in the current turn.
- **Ask before any commit and before any deletion.**
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
| `src/fds/models.py`, `evaluation.py`, `tuning.py` | training and metrics |
| `scripts/00..97_*.py` | pipeline, run in numeric order (see README) |
| `data/rings`, `reports/*.json`, `preds/model=m1_tuned` | committed demo artefacts |
| `api/main.py`, `web/` | demo backend and frontend |

## Session protocol

1. Read this file, `TASKS.md`, tail of `PROGRESS.md`.
2. Do the next unchecked task. Keep changes small.
3. Update `TASKS.md` (tick), append to `PROGRESS.md` (state + next step) and
   `LOG.md` (decisions, numbers, commands, problems). Do this before ending.
