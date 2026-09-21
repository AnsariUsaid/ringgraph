#!/usr/bin/env python
"""Download the IEEE-CIS competition data.

Only the two train files are fetched. The Kaggle ``test_*`` files are unlabelled
(plan.md §Part 2), so the project carves its own splits from train — pulling
``test_transaction.csv`` would cost 613MB for data that is never used.

Requires the competition rules to have been accepted on the website; the API
returns 403 otherwise, regardless of whether the CLI is authenticated.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from fds import paths

COMPETITION = "ieee-fraud-detection"
WANTED = ["train_transaction.csv", "train_identity.csv"]


def kaggle_executable() -> str:
    """Locate the CLI belonging to *this* interpreter.

    Running the script as ``.venv/bin/python scripts/00_download.py`` does not put
    the venv's bin directory on PATH, so a bare ``"kaggle"`` resolves against the
    user's shell PATH or, more often, not at all.
    """
    candidate = Path(sys.executable).parent / "kaggle"
    if candidate.exists():
        return str(candidate)
    found = shutil.which("kaggle")
    if found:
        return found
    sys.exit(
        "the kaggle CLI was not found next to this interpreter or on PATH. "
        "Install it into the venv with: .venv/bin/pip install kaggle"
    )


def fetch(filename: str) -> None:
    target = paths.RAW_DIR / filename
    if target.exists():
        print(f"  {filename}: already present, skipping")
        return

    print(f"  {filename}: downloading")
    result = subprocess.run(
        [
            kaggle_executable(),
            "competitions",
            "download",
            "-c",
            COMPETITION,
            "-f",
            filename,
            "-p",
            str(paths.RAW_DIR),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or "403" in result.stdout + result.stderr:
        sys.exit(
            f"download of {filename} failed.\n{result.stdout}{result.stderr}\n"
            f"A 403 here almost always means the competition rules have not been "
            f"accepted. Open https://www.kaggle.com/c/{COMPETITION} and accept "
            f"them, then re-run."
        )

    archive = paths.RAW_DIR / f"{filename}.zip"
    if archive.exists():
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(paths.RAW_DIR)
        archive.unlink()


def main() -> None:
    paths.ensure(paths.RAW_DIR)
    print(f"fetching {COMPETITION} into {paths.RAW_DIR}")
    for filename in WANTED:
        fetch(filename)
    for filename in WANTED:
        path = paths.RAW_DIR / filename
        print(f"  {filename}: {path.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
