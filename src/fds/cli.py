"""Shared entrypoint surface for ``scripts/``.

Without this each script invents its own argument idiom, and the inconsistency is
very visible to anyone reading the pipeline. Scripts stay thin: parse, resolve
config, make one library call, write one artefact, record the run.
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Any

from fds import paths
from fds.artifacts import git_state
from fds.config import RunConfig, load_config, parse_set_overrides


def base_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--config",
        default=str(paths.CONFIGS_DIR / "default.toml"),
        help="TOML run configuration",
    )
    parser.add_argument(
        "--set",
        dest="overrides",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="dotted-path override, e.g. --set graph.hub_max_degree=500",
    )
    parser.add_argument("--force", action="store_true", help="rebuild even if the output exists")
    return parser


def resolve(args: argparse.Namespace) -> RunConfig:
    """Build the one immutable config this script will use, and print it."""
    cfg = load_config(args.config, parse_set_overrides(args.overrides))
    print(f"run_key={cfg.run_key()}  config={cfg.canonical_json()}")
    return cfg


def record_run(cfg: RunConfig, script: str, metrics: dict[str, Any] | None = None) -> None:
    """Append one line to ``runs/index.jsonl`` — the reproducibility ledger."""
    paths.ensure(paths.RUNS_DIR)
    entry = {
        "run_key": cfg.run_key(),
        "script": script,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "git": git_state(),
        "config": cfg.to_dict(),
        "metrics": metrics or {},
    }
    with paths.RUN_INDEX.open("a") as fh:
        fh.write(json.dumps(entry, default=str) + "\n")
