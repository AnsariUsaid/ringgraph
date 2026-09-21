"""Filesystem layout.

Artefacts are laid out as hive-style partitioned directories rather than long
encoded filenames (D-12): pyarrow recovers the partition keys as columns, a whole
sweep dimension is globbable, and ``tree data/`` renders the sweep space as a
picture.

    data/
      raw/                                            untouched downloads
      base/transactions.parquet                       immutable wide frame
      uid/recipe=<r>/map.parquet                      narrow [TransactionID, uid]
      edges/recipe=<r>/hub=<lo>-<hi>/snap=<dddd>/
      snapfeat/recipe=<r>/hub=<lo>-<hi>/snap=<dddd>/
      attach/recipe=<r>/hub=<lo>-<hi>/cadence=<c>/attach.parquet
      export/kaggle/run=<key>/
    preds/model=<m>/run=<key>/preds.parquet
    reports/
    runs/index.jsonl

Nothing here is tracked by git. ``data/`` and ``reports/`` are created on demand
rather than carrying ``.gitkeep`` files, because git does not honour negation
rules inside an ignored directory (D-04).
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Overridable so the pipeline can point at an external disk without the override
# entering the run key — location is environment, not experiment (D-14, tier 3).
DATA_ROOT = Path(os.environ.get("FDS_DATA_ROOT", PROJECT_ROOT / "data"))

RAW_DIR = DATA_ROOT / "raw"
BASE_DIR = DATA_ROOT / "base"
UID_DIR = DATA_ROOT / "uid"
EDGES_DIR = DATA_ROOT / "edges"
SNAPFEAT_DIR = DATA_ROOT / "snapfeat"
ATTACH_DIR = DATA_ROOT / "attach"
EXPORT_DIR = DATA_ROOT / "export"

PREDS_DIR = PROJECT_ROOT / "preds"
REPORTS_DIR = PROJECT_ROOT / "reports"
RUNS_DIR = PROJECT_ROOT / "runs"
CONFIGS_DIR = PROJECT_ROOT / "configs"

RUN_INDEX = RUNS_DIR / "index.jsonl"

# The two source files, as the Kaggle competition ships them.
RAW_TRANSACTION_CSV = RAW_DIR / "train_transaction.csv"
RAW_IDENTITY_CSV = RAW_DIR / "train_identity.csv"

# The immutable wide frame every later stage reads.
BASE_TRANSACTIONS = BASE_DIR / "transactions.parquet"


def ensure(path: Path) -> Path:
    """Create ``path`` as a directory if absent and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_parent(path: Path) -> Path:
    """Create the parent directory of a file path and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def hub_key(min_degree: int, max_degree: int) -> str:
    return f"{min_degree}-{max_degree}"


def snap_key(end_day_exclusive: int) -> str:
    """Zero-padded so lexical sort over snapshot directories equals temporal sort."""
    return f"{end_day_exclusive:04d}"


def uid_map_path(recipe: str) -> Path:
    return UID_DIR / f"recipe={recipe}" / "map.parquet"


def edges_dir(recipe: str, min_degree: int, max_degree: int, end_day_exclusive: int) -> Path:
    return (
        EDGES_DIR
        / f"recipe={recipe}"
        / f"hub={hub_key(min_degree, max_degree)}"
        / f"snap={snap_key(end_day_exclusive)}"
    )


def snapfeat_dir(recipe: str, min_degree: int, max_degree: int, end_day_exclusive: int) -> Path:
    return (
        SNAPFEAT_DIR
        / f"recipe={recipe}"
        / f"hub={hub_key(min_degree, max_degree)}"
        / f"snap={snap_key(end_day_exclusive)}"
    )


def attach_path(recipe: str, min_degree: int, max_degree: int, cadence_days: int) -> Path:
    return (
        ATTACH_DIR
        / f"recipe={recipe}"
        / f"hub={hub_key(min_degree, max_degree)}"
        / f"cadence={cadence_days}"
        / "attach.parquet"
    )


def preds_path(model: str, run_key: str) -> Path:
    return PREDS_DIR / f"model={model}" / f"run={run_key}" / "preds.parquet"


def report_path(name: str) -> Path:
    return REPORTS_DIR / name
