"""Fraud rate inside the ring catalogue against the base rate (reads data/rings and data/base only; no training)."""
import pandas as pd

R = "data/rings/"
rings = pd.read_parquet(R + "rings.parquet")
mem = pd.read_parquet(R + "members.parquet")
ev = pd.read_parquet(R + "events.parquet")
base = pd.read_parquet("data/base/transactions.parquet", columns=["isFraud"])

tx_base = base["isFraud"].mean()
print(f"base transaction fraud rate {tx_base:.4f}")
print(f"ring clients {len(mem)} in {len(rings)} rings; fraud clients {mem.is_fraud.sum()} -> client fraud rate {mem.is_fraud.mean():.4f}")
print(f"ring transactions {len(ev)}; fraud {ev.is_fraud.sum()} -> txn fraud rate {ev.is_fraud.mean():.4f} ({ev.is_fraud.mean()/tx_base:.1f}x base)")

rings["fraud_rate"] = rings.n_fraud_clients / rings.n_clients
print("rings with >=1 fraud client:", (rings.n_fraud_clients >= 1).sum(), " >=2:", (rings.n_fraud_clients >= 2).sum(),
      " all fraud:", (rings.fraud_rate == 1).sum(), " none:", (rings.n_fraud_clients == 0).sum())

# is the fraud concentrated in a few rings? share of ring fraud clients in rings with >=2 fraud clients
f = mem[mem.is_fraud == 1]
big = rings[rings.n_fraud_clients >= 2].ring_id
print(f"fraud clients inside multi-fraud rings: {f.ring_id.isin(big).sum()} of {len(f)}")

# ranking by structure only (composite excludes labels): fraud client rate in the top-k rings
for k in (25, 50, 100):
    top = rings.sort_values("composite", ascending=False).head(k)
    nc, nf = top.n_clients.sum(), top.n_fraud_clients.sum()
    print(f"top {k} rings by composite: {nf}/{nc} fraud clients = {nf/nc:.3f}")

# size-matched view: fraud rate by ring size band
rings["band"] = pd.cut(rings.n_clients, [2, 3, 5, 10, 1000], labels=["3", "4-5", "6-10", "11+"])
g = rings.groupby("band", observed=True).agg(rings=("ring_id", "size"), clients=("n_clients", "sum"), fraud=("n_fraud_clients", "sum"))
g["rate"] = g.fraud / g.clients
print(g.to_string())

# did fraud come later than the ring formed? test period overlap
ev_t = ev.merge(rings[["ring_id", "first_day"]], on="ring_id")
test = ev_t[ev_t.day >= 151]
print(f"ring txns in the test period (day>=151): {len(test)}, fraud rate {test.is_fraud.mean():.4f}")
