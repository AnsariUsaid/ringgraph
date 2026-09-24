# Relational Fraud Intelligence

Detecting coordinated payment fraud rings through heterogeneous graph structure.

The testable claim: **relational structure between entities is additive** — it recovers
coordinated fraud that a well-tuned tabular model misses, at equal false-positive cost.

---

## Status

Complete. All seven of plan.md's core build steps, plus community detection and
the frontend. The headline result is a **null**: graph structure adds no
measurable lift over a well-tuned tabular baseline. Ring *detection* works; ring
structure does not improve per-transaction *prediction*.

## Stack

| Layer | Choice |
|---|---|
| Python | 3.11 (venv, `.venv/`) |
| Data / ML | pandas, numpy, LightGBM, scikit-learn, Optuna |
| Graph | Neo4j 5.x + Graph Data Science, `neo4j` Python driver |
| GNN (optional M3) | PyTorch + PyTorch Geometric (HGT/RGCN), trained on Kaggle GPU |
| Backend | FastAPI + Uvicorn |
| Frontend | Vite + React + TypeScript, Cytoscape.js (`fcose`), Recharts, TanStack Query |

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

## Reproducing the results

Every result below comes from these commands, in order, against
`configs/default.toml`. Steps 00–10 need the Kaggle credentials above; the rest
are self-contained. Neo4j is needed only for steps 60–63, which produce
diagnostics and the graph render — nothing in the result path depends on it.

```bash
.venv/bin/python scripts/00_download.py          # Kaggle -> data/raw
.venv/bin/python scripts/10_ingest.py            # join, dtypes, day/D1n -> data/base
.venv/bin/python scripts/20_profile.py           # missingness, entity degrees
.venv/bin/python scripts/30_uid_map.py           # client keys, all three recipes
.venv/bin/python scripts/35_hub_band.py          # client degrees -> hub band evidence
.venv/bin/python scripts/40_label_homogeneity.py # THE TRAP A GATE
.venv/bin/python scripts/45_edge_signal.py       # which attributes can carry a ring signal
.venv/bin/python scripts/48_percolation.py       # chooses the degree band and weight floor
.venv/bin/python scripts/50_synchrony.py         # THE COORDINATION GATE
.venv/bin/python scripts/80_snapshot_features.py # Trap B structural features
.venv/bin/python scripts/82_community_features.py
.venv/bin/python scripts/71_tune.py --name m1    # -> configs/tuned/m1.toml (~30 min)
.venv/bin/python scripts/70_train_m1.py --config configs/tuned/m1.toml --name m1_tuned
.venv/bin/python scripts/91_multiseed.py --config configs/tuned/m1.toml   # THE HEADLINE (~40 min)
.venv/bin/python scripts/95_ring_catalogue.py    # -> data/rings/*, what the API serves
.venv/bin/python scripts/96_uid_sensitivity.py   # conclusions across all three recipes
.venv/bin/python scripts/97_shuffle_sanity.py    # leakage check
```

`runs/index.jsonl` records every run with its resolved config and git commit.
Generated artefacts are gitignored, with one deliberate exception: the ~7.6 MB
the API actually reads is committed, so that a clone can run the demo without
reproducing anything. See *Running the demo* below.

## Running the demo

Nothing above is required to do this. The ring catalogue, the reports and the
prediction table for `m1_tuned` are committed — `data/rings/*.parquet`,
`reports/*.json` and `preds/model=m1_tuned/` — so a fresh clone serves the full
frontend immediately. No Kaggle account, no pipeline run, no database.

Committing generated data contradicts the policy above and is a considered
exception: regenerating it needs the competition dataset, credentials and
several hours, and without it every page of the demo is an error state. The
*inputs* stay ignored; only the output the API reads is tracked.

```bash
pip install -r requirements.txt
npm install --prefix web
```

Then two processes. The API serves the ring catalogue from parquet, so Neo4j
does not need to be running for the frontend to work — nothing in the serving
path touches it.

```bash
.venv/bin/uvicorn api.main:app --port 8000
```

```bash
npm run dev --prefix web
```

Then open http://localhost:5173.

## Findings

| | |
|---|---|
| Trap A | Confirmed. 96.6% of multi-transaction clients are label-pure against 85.1% expected by chance, so the thesis is restricted to cross-client structure. |
| Usable links | Device attributes only. `card1`, `card2`, `addr1` and `P_emaildomain` all disperse fraud rather than concentrating it. |
| Coordination | Real. Fraud-bearing components are 3-4x more temporally synchronised than fraud-free components of the same size. |
| Rings found | 550 candidates, 112 holding two or more fraud clients, 12 entirely fraudulent against a 3.7% base rate. |
| Predictive lift | **None.** Two independent structural feature families, five seeds each, every stratum inside the noise floor. |

**Ring detection works; ring structure does not improve per-transaction
prediction.** The negative result is the headline, and the machinery that makes
it credible is the point: a temporal guard enforced as a test rather than a
convention, a graph that never receives labels, and a measured training-noise
floor that a single-run comparison would have hidden behind.

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
| M3 | Graph-native | Heterogeneous GNN — *not implemented*; plan.md names it the first thing to cut, and the M2 null gives no reason to expect a GNN over the same graph to do better |

Primary metric is **TPR at fixed FPR (1% and 0.1%)**, with bootstrap confidence intervals on the
*difference* between models rather than two separate point estimates.

## Layout

```
src/fds/      importable library (config, entity reconstruction, graph, features, models, eval)
scripts/      numbered pipeline entrypoints, run in order
api/          FastAPI service over the precomputed ring catalogue (parquet, not Neo4j)
web/          React frontend
tests/        leakage and invariant tests
data/         raw → interim → processed (gitignored, except data/rings/)
reports/      generated analysis output (*.json tracked; the API reads them)
preds/        per-model prediction tables (only model=m1_tuned tracked)
```
