"""Parquet artefacts with manifest sidecars.

Stale files in a research pipeline are unavoidable. *Silently reading* one is
not, and that is the whole job of this module (D-12).

Every artefact written here gets a ``_manifest.json`` beside it, produced by the
same call that writes the parquet — never by a separate step, because separate
steps get skipped. The manifest records the resolved parameters that produced the
file, the git commit and whether the tree was dirty, the content hashes of every
input, and the shape of the result.

Two levels of checking, so the fast path stays fast:

* ``read_parquet`` always enforces ``schema_version``. Bump that integer when a
  column contract changes and every older file is refused outright rather than
  loaded into code that expects different columns.
* ``verify_inputs`` re-hashes the recorded inputs on demand. Content hashing a
  multi-hundred-megabyte parquet costs a second or two, which is fine once at the
  start of a script and wasteful on every load.
"""

from __future__ import annotations

import json
import subprocess
import time
import warnings
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import pandas as pd

MANIFEST_NAME = "_manifest.json"
_HASH_CHUNK = 1 << 20


class StaleArtifactError(RuntimeError):
    """Raised when an artefact on disk cannot be trusted for the current code."""


@dataclass(frozen=True)
class InputRef:
    """A file this artefact was derived from, with the digest it had at write time."""

    path: str
    sha256: str
    bytes: int


def file_digest(path: Path | str) -> str:
    h = sha256()
    with Path(path).open("rb") as fh:
        while chunk := fh.read(_HASH_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def input_ref(path: Path | str) -> InputRef:
    p = Path(path)
    return InputRef(path=str(p), sha256=file_digest(p), bytes=p.stat().st_size)


def git_state() -> dict[str, Any]:
    """Commit and dirty flag, so an artefact can be traced to the code that made it."""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
            ).stdout.strip()
        )
        return {"commit": sha, "dirty": dirty}
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"commit": None, "dirty": None}


def manifest_path(parquet_path: Path | str) -> Path:
    return Path(parquet_path).parent / MANIFEST_NAME


def write_parquet(
    df: pd.DataFrame,
    path: Path | str,
    *,
    schema_version: int,
    params: dict[str, Any] | None = None,
    inputs: list[InputRef] | None = None,
    extra: dict[str, Any] | None = None,
    compression: str = "zstd",
) -> Path:
    """Write a dataframe and its manifest atomically enough to be trustworthy.

    The parquet lands first, then the manifest. If the process dies between the
    two, the next read finds a parquet with no manifest and warns — which is the
    correct outcome, since a file with no provenance is exactly what should not be
    trusted silently.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    df.to_parquet(path, compression=compression, index=False)
    elapsed = time.perf_counter() - started

    manifest = {
        "schema_version": schema_version,
        "artifact": path.name,
        "written_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "write_seconds": round(elapsed, 3),
        "rows": len(df),
        "columns": list(df.columns),
        "n_columns": int(df.shape[1]),
        "bytes": path.stat().st_size,
        "params": params or {},
        "inputs": [vars(i) for i in (inputs or [])],
        "git": git_state(),
        "versions": {"pandas": pd.__version__},
        **(extra or {}),
    }
    manifest_path(path).write_text(json.dumps(manifest, indent=2, default=str) + "\n")
    return path


def read_manifest(path: Path | str) -> dict[str, Any] | None:
    mp = manifest_path(path)
    if not mp.exists():
        return None
    return json.loads(mp.read_text())


def read_parquet(
    path: Path | str,
    *,
    expect_schema_version: int | None = None,
    columns: list[str] | None = None,
    strict: bool = False,
) -> pd.DataFrame:
    """Load an artefact, refusing one written under a different column contract."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is missing. It is produced by an earlier pipeline step; "
            f"run that step rather than creating the file by hand."
        )

    manifest = read_manifest(path)
    if manifest is None:
        message = f"{path} has no {MANIFEST_NAME}; its provenance is unknown."
        if strict:
            raise StaleArtifactError(message)
        warnings.warn(message, stacklevel=2)
    elif expect_schema_version is not None:
        found = manifest.get("schema_version")
        if found != expect_schema_version:
            raise StaleArtifactError(
                f"{path} was written under schema_version {found}, but this code "
                f"expects {expect_schema_version}. Delete the artefact and rebuild "
                f"it; its column contract has changed."
            )

    return pd.read_parquet(path, columns=columns)


def verify_inputs(path: Path | str) -> list[str]:
    """Re-hash the recorded inputs and return a list of human-readable drifts.

    An empty list means every input is byte-identical to what produced this
    artefact. Called explicitly at the top of a script rather than on every load,
    because content hashing is too slow to do casually.
    """
    manifest = read_manifest(path)
    if manifest is None:
        return [f"{path}: no manifest, cannot verify"]

    problems: list[str] = []
    for ref in manifest.get("inputs", []):
        source = Path(ref["path"])
        if not source.exists():
            problems.append(f"input {source} no longer exists")
            continue
        if file_digest(source) != ref["sha256"]:
            problems.append(f"input {source} has changed since {path} was written")
    return problems
