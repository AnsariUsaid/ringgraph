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
