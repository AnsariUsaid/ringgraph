"""FastAPI service behind the investigation frontend.

Serves the ring catalogue from parquet rather than querying Neo4j per request.
The catalogue is small (550 rings, 4,762 clients) and precomputed, so a request
is a dataframe filter rather than a graph traversal -- which removes the
cold-cache latency that would otherwise show up as a stutter on the first click
of a demo, and means the frontend works whether or not the database is running.

Entity ids are namespaced (``client:7f3a``, ``attr:DeviceInfo:Windows``) so that
the Cytoscape node id, the URL token and the query key are the same string and
``id.split(':')[0]`` gives the type.

Fraud labels are served for *display* only. They never entered the graph and
never entered a structural feature; the frontend shows them the way an analyst
reviewing a closed case would.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from fds import paths

app = FastAPI(title="Relational Fraud Intelligence", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

AXES = ("density", "synchrony", "concentration", "tightness")


@lru_cache(maxsize=1)
def catalogue() -> dict[str, pd.DataFrame]:
    """Load every catalogue table once, at first request."""
    tables = {}
    for name in ("rings", "members", "attributes", "events", "edges"):
        path = paths.RINGS_DIR / f"{name}.parquet"
        if not path.exists():
            raise RuntimeError(f"{path} missing -- run scripts/95_ring_catalogue.py")
        tables[name] = pd.read_parquet(path)
    return tables


@lru_cache(maxsize=1)
def model_reports() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in ("multiseed_m1_vs_m2", "multiseed_m1_vs_m2_community", "m1_tuned_metrics"):
        path = paths.report_path(f"{name}.json")
        if path.exists():
            out[name] = json.loads(path.read_text())
    return out


def _client_id(uid: str) -> str:
    return f"client:{uid}"


def _attr_id(kind: str, value: str) -> str:
    return f"attr:{kind}:{value}"


@app.get("/health")
def health() -> dict[str, Any]:
    tables = catalogue()
    return {
        "status": "ok",
        "rings": len(tables["rings"]),
        "clients": int(tables["members"]["uid"].nunique()),
    }


@app.get("/rings")
def list_rings(
    limit: int = Query(100, ge=1, le=550),
    min_clients: int = Query(3, ge=2),
    sort: str = Query("composite"),
) -> dict[str, Any]:
    """Ranked candidate rings.

    Sorting defaults to plan.md's composite. The per-axis options exist because
    measurement showed the composite is dragged below its best component by two
    anti-predictive axes (D-45) -- the frontend lets a reader see that directly
    rather than taking it on trust.
    """
    rings = catalogue()["rings"]
    if sort not in {*AXES, "composite", "n_clients", "n_transactions", "burst_share"}:
        raise HTTPException(400, f"cannot sort by {sort!r}")

    frame = rings[rings["n_clients"] >= min_clients].sort_values(sort, ascending=False)
    frame = frame.head(limit)
    return {
        "total": len(rings),
        "returned": len(frame),
        "sort": sort,
        "rings": [
            {
                "ring_id": int(r["ring_id"]),
                "n_clients": int(r["n_clients"]),
                "n_transactions": int(r["n_transactions"]),
                "n_fraud_clients": int(r["n_fraud_clients"]),
                "fraud_share": float(r["fraud_share"]),
                "composite": float(r["composite"]),
                "span_days": int(r["span_days"]),
                "total_amount": float(r["total_amount"]),
                "axes": {axis: float(r[f"pct_{axis}"]) for axis in AXES},
                "raw": {axis: float(r[axis]) for axis in AXES},
            }
            for _, r in frame.iterrows()
        ],
    }


def _ring_or_404(ring_id: int) -> pd.Series:
    rings = catalogue()["rings"]
    match = rings[rings["ring_id"] == ring_id]
    if match.empty:
        raise HTTPException(404, f"ring {ring_id} not found")
    return match.iloc[0]


@app.get("/rings/{ring_id}")
def ring_detail(ring_id: int) -> dict[str, Any]:
    ring = _ring_or_404(ring_id)
    tables = catalogue()
    members = tables["members"]
    members = members[members["ring_id"] == ring_id]
    attributes = tables["attributes"]
    attributes = attributes[attributes["ring_id"] == ring_id]

    shared = (
        attributes.groupby(["type", "value"], observed=True)["uid"]
        .nunique()
        .reset_index(name="n_clients")
        .sort_values("n_clients", ascending=False)
    )
    return {
        "ring_id": ring_id,
        "n_clients": int(ring["n_clients"]),
        "n_transactions": int(ring["n_transactions"]),
        "n_fraud_clients": int(ring["n_fraud_clients"]),
        "fraud_share": float(ring["fraud_share"]),
        "composite": float(ring["composite"]),
        "first_day": int(ring["first_day"]),
        "last_day": int(ring["last_day"]),
        "span_days": int(ring["span_days"]),
        "total_amount": float(ring["total_amount"]),
        "axes": {axis: float(ring[f"pct_{axis}"]) for axis in AXES},
        "raw": {axis: float(ring[axis]) for axis in AXES},
        "burst_share": float(ring["burst_share"]),
        "n_shared_attributes": len(shared),
        "shared_attributes": [
            {
                "id": _attr_id(r["type"], r["value"]),
                "type": r["type"],
                "value": str(r["value"]),
                "n_clients": int(r["n_clients"]),
            }
            for _, r in shared.head(20).iterrows()
        ],
        "members": [
            {
                "id": _client_id(r["uid"]),
                "uid": r["uid"],
                "n_transactions": int(r["n_transactions"]),
                "total_amount": float(r["total_amount"]),
                "first_day": int(r["first_day"]),
                "last_day": int(r["last_day"]),
                "is_fraud": bool(r["is_fraud"]),
            }
            for _, r in members.sort_values("first_day").iterrows()
        ],
    }


@app.get("/rings/{ring_id}/subgraph")
def ring_subgraph(ring_id: int, include_attributes: bool = True) -> dict[str, Any]:
    """Cytoscape elements for one ring."""
    _ring_or_404(ring_id)
    tables = catalogue()
    members = tables["members"]
    members = members[members["ring_id"] == ring_id]
    edges = tables["edges"]
    edges = edges[edges["ring_id"] == ring_id]
    attributes = tables["attributes"]
    attributes = attributes[attributes["ring_id"] == ring_id]

    nodes = [
        {
            "data": {
                "id": _client_id(r["uid"]),
                "kind": "Client",
                "label": r["uid"][:8],
                "uid": r["uid"],
                "n_transactions": int(r["n_transactions"]),
                "is_fraud": bool(r["is_fraud"]),
            }
        }
        for _, r in members.iterrows()
    ]
    elements = list(nodes)
    for _, r in edges.iterrows():
        elements.append(
            {
                "data": {
                    "id": f"link:{r['source'][:8]}-{r['target'][:8]}",
                    "source": _client_id(r["source"]),
                    "target": _client_id(r["target"]),
                    "kind": "LINKED",
                    "weight": int(r["weight"]),
                    "attributes": r["attributes"],
                }
            }
        )

    if include_attributes:
        shared = (
            attributes.groupby(["type", "value"], observed=True)["uid"]
            .nunique()
            .reset_index(name="n_clients")
        )
        shared = shared[shared["n_clients"] >= 2]
        for _, r in shared.iterrows():
            elements.append(
                {
                    "data": {
                        "id": _attr_id(r["type"], r["value"]),
                        "kind": r["type"],
                        "label": str(r["value"])[:18],
                        "n_clients": int(r["n_clients"]),
                    }
                }
            )
        held = attributes.merge(shared[["type", "value"]], on=["type", "value"])
        for _, r in held.iterrows():
            elements.append(
                {
                    "data": {
                        "id": f"has:{r['uid'][:8]}:{r['type']}:{r['value']}"[:80],
                        "source": _client_id(r["uid"]),
                        "target": _attr_id(r["type"], r["value"]),
                        "kind": "HAS_ATTRIBUTE",
                    }
                }
            )

    return {"ring_id": ring_id, "elements": elements, "n_nodes": len(nodes)}


@app.get("/rings/{ring_id}/events")
def ring_timeline(ring_id: int) -> dict[str, Any]:
    """Per-transaction events for the temporal strip, one lane per client."""
    _ring_or_404(ring_id)
    events = catalogue()["events"]
    events = events[events["ring_id"] == ring_id]
    if events.empty:
        return {"ring_id": ring_id, "lanes": [], "t_min": 0, "t_max": 0}

    order = events.groupby("uid", observed=True)["TransactionDT"].min().sort_values()
    lanes = [
        {
            "id": _client_id(uid),
            "uid": uid,
            "events": [
                {
                    "t": int(e["TransactionDT"]),
                    "day": int(e["day"]),
                    "amount": float(e["TransactionAmt"]),
                    "is_fraud": bool(e["is_fraud"]),
                }
                for _, e in events[events["uid"] == uid].sort_values("TransactionDT").iterrows()
            ],
        }
        for uid in order.index
    ]
    return {
        "ring_id": ring_id,
        "t_min": int(events["TransactionDT"].min()),
        "t_max": int(events["TransactionDT"].max()),
        "lanes": lanes,
    }


@app.get("/metrics/models")
def metrics_models() -> dict[str, Any]:
    """The headline comparison, reported as it came out.

    Returns the multi-seed distributions rather than single point estimates,
    because seed-only variation on this problem (0.033 in TPR@1%FPR) exceeds
    every model difference measured (D-42).
    """
    reports = model_reports()
    if "multiseed_m1_vs_m2" not in reports:
        raise HTTPException(503, "multiseed comparison not built yet")
    return {
        "structural": reports["multiseed_m1_vs_m2"]["summary"],
        "community": reports.get("multiseed_m1_vs_m2_community", {}).get("summary"),
        "seed_note": (
            "Differences are reported against a measured training-noise floor. "
            "A single training run varies by 0.033 in TPR@1%FPR on this data, "
            "which is larger than any model difference observed."
        ),
    }


@app.get("/metrics/axes")
def metrics_axes(k: int = Query(50, ge=10, le=300)) -> dict[str, Any]:
    """How well each Part 5 axis ranks rings by fraud content.

    Reports a **size-controlled** enrichment rather than the share of top-ranked
    rings holding two or more fraud clients. That earlier statistic was
    dominated by ring size -- at the fraud rate among ring members, a ten-client
    ring clears it 60% of the time by chance alone -- so a size-only ranking
    scored highly for tautological reasons, and the shuffle test caught it by
    scoring *higher* on destroyed labels (D-47).

    Enrichment divides observed fraud clients by the number expected from ring
    size, so a ranking that merely sorts by size scores 1.0.
    """
    rings = catalogue()["rings"]
    rate = float(rings["n_fraud_clients"].sum() / rings["n_clients"].sum())
    out = {}
    for axis in (*AXES, "composite", "n_clients", "burst_share"):
        top = rings.sort_values(axis, ascending=False).head(k)
        expected = float(top["n_clients"].sum()) * rate
        out[axis] = {
            "enrichment": (
                float(top["n_fraud_clients"].sum() / expected) if expected else float("nan")
            ),
            "observed_fraud_clients": int(top["n_fraud_clients"].sum()),
            "expected_fraud_clients": expected,
        }
    return {"client_fraud_rate": rate, "k": k, "n_rings": len(rings), "axes": out}


@app.get("/metrics/sweep")
def metrics_sweep(
    model: str = Query("m1_tuned", pattern=r"^[A-Za-z0-9_]+$"),
    points: int = Query(512, ge=16, le=2048),
) -> dict[str, Any]:
    """Full threshold sweep, so the frontend slider needs no network per frame.

    Returning the whole curve once (a few tens of kB) instead of a request per
    drag frame is what keeps the threshold control at 60fps and lets it survive
    a backend hiccup mid-demo (D-25).
    """
    # `model` is interpolated into a path, so it is pattern-restricted above to
    # word characters -- otherwise "../.." walks out of the predictions tree.
    # `points` is bounded because the loop below is O(points x test rows), and
    # an unbounded value would hang the server on a single request.
    candidates = sorted((paths.PREDS_DIR / f"model={model}").glob("run=*/preds.parquet"))
    if not candidates:
        raise HTTPException(404, f"no predictions for model {model!r}")
    # Newest run wins. mtime rather than the run key because the key is a hash
    # of the config, not a timestamp, so it carries no ordering.
    preds = pd.read_parquet(max(candidates, key=lambda p: p.stat().st_mtime))
    test = preds[preds["split"] == "test"]
    y = test["y_true"].to_numpy()
    scores = test["y_score"].to_numpy()

    thresholds = np.quantile(scores, np.linspace(0, 1, points))
    positives, negatives = int(y.sum()), int((y == 0).sum())
    rows = []
    for threshold in thresholds:
        flagged = scores >= threshold
        tp = int((flagged & (y == 1)).sum())
        fp = int((flagged & (y == 0)).sum())
        rows.append(
            {
                "threshold": float(threshold),
                "tp": tp,
                "fp": fp,
                "fn": positives - tp,
                "tn": negatives - fp,
                "tpr": tp / positives if positives else 0.0,
                "fpr": fp / negatives if negatives else 0.0,
                "precision": tp / (tp + fp) if (tp + fp) else 0.0,
            }
        )
    return {"model": model, "n": len(test), "positives": positives, "sweep": rows}
