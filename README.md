# Relational Fraud Intelligence

Detecting coordinated payment fraud rings through heterogeneous graph structure.

The testable claim: **relational structure between entities is additive** — it recovers
coordinated fraud that a well-tuned tabular model misses, at equal false-positive cost.

---

## Status

Phase 0 — scaffold. No data ingested yet.

## Stack

| Layer | Choice |
|---|---|
| Python | 3.11 (venv, `.venv/`) |
| Data / ML | pandas, numpy, LightGBM, scikit-learn, Optuna |
| Graph | Neo4j 5.x + Graph Data Science, `neo4j` Python driver |
| GNN (optional M3) | PyTorch + PyTorch Geometric (HGT/RGCN), trained on Kaggle GPU |
| Backend | FastAPI + Uvicorn |
| Frontend | Vite + React + TypeScript, Cytoscape.js (`fcose`), Tailwind, Recharts |

## Dataset

[IEEE-CIS Fraud Detection](https://www.kaggle.com/c/ieee-fraud-detection) — ~590,540
transactions, ~3.5% fraud, joined to identity attributes covering ~24% of rows.

The data is **not committed**. To obtain it:

1. Create a Kaggle account and accept the competition rules on the competition page.
2. Kaggle → Settings → API → *Create New Token*, then save the file to `~/.kaggle/kaggle.json`.
3. Run the download script (see *Setup*).

## Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

All Python work runs inside `.venv`.

## Method notes

Two failure modes are designed around rather than disclosed after the fact:

- **Per-client labelling.** Fraud labels in this dataset are reported to be assigned per client,
  not per transaction, which clusters fraud on client identity by construction. Within-client
  structure is therefore treated as baseline enrichment only; the thesis rests on **cross-client**
  structure — distinct reconstructed identities linked by a shared device, address, card
  attribute or email.
- **Temporal leakage through graph features.** A structural feature attached to a transaction at
  time *t* may only be computed from the graph restricted to transactions strictly before *t*.
  Enforced by expanding-window snapshots and asserted in the test suite.

Splits are strictly temporal: train days 0–119, validation 120–150, test 151–181.

## Models

| | Model | Inputs |
|---|---|---|
| M1 | LightGBM baseline | Tabular only |
| M2 | Structure-augmented | M1 + graph structural features |
| M3 | Graph-native | Heterogeneous GNN over the Neo4j-derived graph |

Primary metric is **TPR at fixed FPR (1% and 0.1%)**, with bootstrap confidence intervals on the
*difference* between models rather than two separate point estimates.

## Layout

```
src/fds/      importable library (config, entity reconstruction, graph, features, models, eval)
scripts/      numbered pipeline entrypoints, run in order
api/          FastAPI service over Neo4j
web/          React frontend
tests/        leakage and invariant tests
data/         raw → interim → processed (gitignored, created at runtime)
reports/      generated analysis output (gitignored)
```
