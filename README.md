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

> **Update (session 2):** that null is for label-free structure. Adding *delayed fraud
> labels* (fraud the bank already knew about) does lift detection; see
> *Update: delayed-label results* under Findings below. The original text is kept as written.

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

Delayed-label extension (session 2). Controls and graph models are tuned on validation
only, with M1's search space. M1 is never changed.

```bash
.venv/bin/python scripts/83_label_features.py        # control lfc, device graph lfg, aggregates lfa
.venv/bin/python scripts/84_relational_features.py   # rl delayed exposure, rs behaviour, rp 2-hop
.venv/bin/python scripts/86_client_profile.py        # cp causal client profile
.venv/bin/python scripts/87_offline_features.py      # whole-dataset label-free features (offline setting)
.venv/bin/python scripts/94_tune_graph.py            # -> configs/tuned/ctrl_d30.toml, graph_d30.toml
.venv/bin/python scripts/93_graph_sweep.py --config configs/tuned/m1.toml --delays 30 --ablations
.venv/bin/python scripts/93_graph_sweep.py --config configs/tuned/m1.toml --delays 90 --seeds 11 22 33
.venv/bin/python scripts/96_offline_ladder.py --config configs/tuned/m1.toml
.venv/bin/python scripts/98_summary.py               # prints the table, writes reports/headline.json
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

### Update: delayed-label results

The null above is for *label-free* graph structure. The extension below adds knowledge the
bank genuinely had: a fraud label may enter a feature for a transaction at time *t* only if
it was confirmed at or before *t* minus the chargeback delay (enforced by leakage tests).
Three models are always shown side by side so the graph is never credited with what is
really client history:

- **normal (M1)**: one transaction at a time, unchanged.
- **control**: M1 plus delayed history on tabular keys only (card1, addr1, email, uid).
- **graph**: control plus shared-entity exposure, ring breadth and recency, neighbourhood
  behaviour, two-hop propagation and a causal client profile.

**Causal (deployable) setting**: only earlier rows and labels confirmed by *t*. Test split,
TPR at 1% FPR, mean over seeds (5 for 14d/30d, 3 for 7d/60d/90d), paired bootstrap;
`*` = 95% interval excludes zero.

| Delay | normal (M1) | control | graph | graph vs normal | graph vs control | TPR@0.1%FPR, M1 to graph |
|---|---|---|---|---|---|---|
| 7d | 0.426 | 0.619 | 0.636 | +0.192* (+49%) | +0.016* | 0.233 to 0.375 |
| 14d | 0.426 | 0.584 | 0.603 | +0.165* (+42%) | +0.023* | 0.233 to 0.336 |
| **30d** (realistic) | 0.426 | 0.538 | 0.560 | +0.120* (+31%) | +0.027* | 0.233 to 0.310 |
| 60d | 0.426 | 0.501 | 0.509 | +0.065* (+19%) | +0.005 | 0.233 to 0.268 |
| 90d | 0.426 | 0.472 | 0.478 | +0.040* (+12%) | +0.007 | 0.233 to 0.250 |

At 30d the graph catches 1,743 of the 3,114 test frauds against 1,327 for M1 at the
same 1% false-alarm rate. At 14d, 1,877 against 1,327 (precision 0.69 against 0.61).

**Offline / retrospective setting** (Kaggle-style: whole-dataset label-free aggregates,
test labels never used; 30d delay, 5 seeds):

| Level | TPR@1% | TPR@0.1% | $ recall@1% | precision@1% |
|---|---|---|---|---|
| L0 normal (M1) | 0.426 | 0.233 | 0.346 | 0.606 |
| L1 + whole-dataset client aggregates | 0.500* | 0.254 | 0.410 | 0.644 |
| L2 + own-client delayed history | 0.547* | 0.317* | 0.441 | 0.664 |
| L3 + graph features | 0.556* | 0.331 | 0.456 | 0.668 |
| L4 + client smoothing | 0.556 | 0.331 | 0.456 | 0.668 |

Smoothing (mean or max, chosen on validation) adds nothing: L4 minus L3 is -0.0006 at 1% FPR.

**Ablations at 30d, TPR@1%FPR** (M1 plus one family): label-free neighbourhood behaviour
0.434, client profile 0.448, delayed multi-key exposure 0.553, plus two-hop 0.552. Nearly all
of the lift is delayed exposure. Risk propagation was tested and dropped (no validation gain).

**Honest attribution.**

- Graph beats M1 by +12% to +49% relative, significantly, at every delay.
- Most of that is delayed own-client history, a tabular key, which the control already has.
  The graph's own contribution is smaller: +0.016 to +0.027 at 7d to 30d (significant), not
  significant at 60d and 90d, and not significant at 0.1% FPR at 30d.
- About 79% of fraud is first-time fraud with no link to any known fraud, so key-sharing links
  cannot give a large margin over client history. For clients with no history, nothing helps.
- The gain over M1 shrinks as the delay grows, because less confirmed fraud has reached the
  features by the time a transaction arrives.
- Tuned on validation only. Validation scores run higher than test for all three models
  (30d: M1 0.497 to 0.426, control 0.596 to 0.538, graph 0.611 to 0.560), with similar gaps.

Numbers: `reports/headline.json` (all of the above), `reports/graph_sweep_tuned_d*.json`,
`reports/offline_ladder.json`, `reports/offline_smoothing.json`.

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
