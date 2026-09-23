"""Client-to-client links from shared identity attributes.

Per D-38 the graph's cross-client edges come from the identity block, not from
card or address attributes. Two design points carried from that decision:

* **One weighted edge, not one node per attribute combination.** Each attribute
  that two clients share contributes 1 to the edge weight. A concatenated
  fingerprint would be a hard AND — one null kills the link and it cannot express
  "these clients match on 5 of 6 attributes". The weight also doubles as the
  percolation control that degree banding alone cannot provide.

* **Degrees are counted over whatever transaction set is passed in.** For the
  pipeline that set is a snapshot (D-07); for a global diagnostic it is
  everything. This module never filters by day itself — ``fds.snapshots`` owns
  that, and duplicating the filter here would break the Trap B guarantee.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import pandas as pd

# Identity-block attributes that are independent of every uid recipe, so an edge
# built from them is recipe-invariant (D-38).
IDENTITY_LINK_COLUMNS: tuple[str, ...] = (
    "DeviceInfo",
    "id_31",
    "id_33",
    "id_30",
    "id_17",
    "id_19",
    "id_20",
    "id_13",
)


@dataclass(frozen=True)
class LinkParams:
    min_degree: int = 2
    max_degree: int = 100
    min_weight: int = 1


# Frozen, so sharing one instance as a default is safe.
DEFAULT_LINK_PARAMS = LinkParams()


def attribute_pairs(entity: pd.Series, uid: pd.Series, params: LinkParams) -> pd.DataFrame:
    """All distinct client pairs co-occurring on one attribute's values.

    Values outside the degree band are dropped: below ``min_degree`` they link
    nothing, above ``max_degree`` they are hubs that would fuse the graph into
    the single blob plan.md warns about.
    """
    frame = pd.DataFrame({"entity": entity.to_numpy(), "uid": uid.to_numpy()}).dropna()
    frame = frame.drop_duplicates()
    sizes = frame.groupby("entity", observed=True)["uid"].nunique()
    keep = sizes[(sizes >= params.min_degree) & (sizes <= params.max_degree)].index
    frame = frame[frame["entity"].isin(keep)]
    if frame.empty:
        return pd.DataFrame(columns=["a", "b"])

    rows: list[tuple[str, str]] = []
    for _, members in frame.groupby("entity", observed=True)["uid"]:
        uids = sorted(set(members))
        rows.extend(combinations(uids, 2))
    if not rows:
        return pd.DataFrame(columns=["a", "b"])
    return pd.DataFrame(rows, columns=["a", "b"])


def build_links(
    df: pd.DataFrame,
    uid_column: str,
    columns: tuple[str, ...] = IDENTITY_LINK_COLUMNS,
    params: LinkParams = DEFAULT_LINK_PARAMS,
) -> pd.DataFrame:
    """Collapse per-attribute pairs into one weighted edge list.

    Returns ``[a, b, weight, attributes]`` where ``weight`` counts how many
    attributes the two clients share. ``attributes`` is kept because the evidence
    panel must be able to say *which* attributes matched, not merely that some did.
    """
    frames = []
    for column in columns:
        if column not in df.columns:
            continue
        pairs = attribute_pairs(df[column], df[uid_column], params)
        if not pairs.empty:
            frames.append(pairs.assign(attribute=column))
    if not frames:
        return pd.DataFrame(columns=["a", "b", "weight", "attributes"])

    stacked = pd.concat(frames, ignore_index=True)
    grouped = stacked.groupby(["a", "b"], observed=True)["attribute"]
    edges = pd.DataFrame(
        {
            "weight": grouped.nunique(),
            "attributes": grouped.apply(lambda s: ",".join(sorted(set(s)))),
        }
    ).reset_index()
    return edges[edges["weight"] >= params.min_weight].reset_index(drop=True)


class _UnionFind:
    def __init__(self, items: list[str]) -> None:
        self.parent = dict.fromkeys(items)
        for item in items:
            self.parent[item] = item

    def find(self, x: str) -> str:
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:  # path compression
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, x: str, y: str) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx != ry:
            self.parent[ry] = rx


def connected_components(edges: pd.DataFrame) -> pd.DataFrame:
    """Assign a component id to every client appearing in the edge list.

    plan.md's verification rule requires the largest component to hold a sane
    share of nodes; ``component_summary`` reports that, because transitive
    linkage can percolate into a giant component even when every individual
    entity respects the degree ceiling.
    """
    if edges.empty:
        return pd.DataFrame(columns=["uid", "component"])
    nodes = pd.unique(pd.concat([edges["a"], edges["b"]], ignore_index=True)).tolist()
    uf = _UnionFind(nodes)
    for a, b in zip(edges["a"].to_numpy(), edges["b"].to_numpy(), strict=True):
        uf.union(a, b)
    roots = pd.Series([uf.find(n) for n in nodes])
    codes, _ = pd.factorize(roots)
    return pd.DataFrame({"uid": nodes, "component": codes.astype("int32")})


def component_summary(members: pd.DataFrame, client_label: pd.Series) -> pd.DataFrame:
    """Per-component size and fraud composition."""
    joined = members.assign(is_fraud=members["uid"].map(client_label).fillna(0).astype(int))
    grouped = joined.groupby("component", observed=True)["is_fraud"]
    out = pd.DataFrame({"n_clients": grouped.size(), "n_fraud_clients": grouped.sum()})
    out["fraud_share"] = out["n_fraud_clients"] / out["n_clients"]
    return out.reset_index()


def percolation_report(members: pd.DataFrame) -> dict[str, float | int]:
    if members.empty:
        return {"n_components": 0}
    sizes = members.groupby("component", observed=True).size()
    n_linked = int(sizes.sum())
    return {
        "n_components": int(sizes.size),
        "n_linked_clients": n_linked,
        "largest_component": int(sizes.max()),
        "largest_component_share": float(sizes.max() / n_linked),
        "median_component_size": float(sizes.median()),
        "n_components_ge_3": int((sizes >= 3).sum()),
    }
