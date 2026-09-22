"""Neo4j connection handling.

Credentials come from the environment (a gitignored ``.env``), never from the
run config — they are machine state, not experiment state, and including them in
the run key would give the same experiment different keys on different machines.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any

from dotenv import load_dotenv
from neo4j import GraphDatabase

from fds import paths

load_dotenv(paths.PROJECT_ROOT / ".env")


def connection_settings() -> dict[str, str]:
    password = os.environ.get("NEO4J_PASSWORD", "")
    if not password:
        raise RuntimeError(
            "NEO4J_PASSWORD is not set. Copy .env.example to .env and fill it in; "
            ".env is gitignored so the password never reaches version control."
        )
    return {
        "uri": os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        "user": os.environ.get("NEO4J_USER", "neo4j"),
        "password": password,
        "database": os.environ.get("NEO4J_DATABASE", "neo4j"),
    }


@contextmanager
def driver():
    settings = connection_settings()
    drv = GraphDatabase.driver(settings["uri"], auth=(settings["user"], settings["password"]))
    try:
        yield drv, settings["database"]
    finally:
        drv.close()


def run(query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    with driver() as (drv, database), drv.session(database=database) as session:
        return [record.data() for record in session.run(query, parameters or {})]


def server_report() -> dict[str, Any]:
    """Versions and capability checks, so surprises surface before a long load."""
    report: dict[str, Any] = {}
    components = run("CALL dbms.components() YIELD name, versions, edition")
    for row in components:
        report[row["name"]] = {"version": row["versions"][0], "edition": row["edition"]}

    try:
        gds = run("RETURN gds.version() AS version")
        report["gds_version"] = gds[0]["version"]
    except Exception as exc:
        report["gds_version"] = f"UNAVAILABLE: {exc}"

    # plan.md §Part 3 asks this to be verified rather than assumed: Leiden has
    # historically been Enterprise-tier, with Louvain as the safe fallback.
    try:
        procs = run(
            "SHOW PROCEDURES YIELD name WHERE name STARTS WITH 'gds.' "
            "AND (name CONTAINS 'leiden' OR name CONTAINS 'louvain' "
            "OR name CONTAINS 'pageRank' OR name CONTAINS 'wcc') RETURN name"
        )
        report["algorithms"] = sorted({p["name"] for p in procs})
    except Exception as exc:
        report["algorithms"] = f"UNAVAILABLE: {exc}"

    report["memory"] = run(
        "CALL dbms.listConfig() YIELD name, value "
        "WHERE name IN ['server.memory.heap.max_size','server.memory.pagecache.size'] "
        "RETURN name, value"
    )
    return report
