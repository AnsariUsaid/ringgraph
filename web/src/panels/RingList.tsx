import { useQuery } from "@tanstack/react-query";
import { api, queryKeys } from "../api/client";
import { RiskSignature } from "../components/RiskSignature";
import { StatePanel } from "../components/StatePanel";
import { useSelection } from "../store/selection";
import { riskColor } from "../lib/risk";

// Every axis the API can sort by. Exposing them is the point: measurement
// showed the composite ranks below its own best component, and a reader should
// be able to see that by clicking rather than take it on trust (D-48).
const SORTS = [
  { key: "composite", label: "Composite" },
  { key: "burst_share", label: "Burst" },
  { key: "synchrony", label: "Sync" },
  { key: "density", label: "Density" },
  { key: "tightness", label: "Amount" },
  { key: "n_clients", label: "Size" },
];

export function RingList({ sort, onSortChange }: { sort: string; onSortChange: (s: string) => void }) {
  const ringId = useSelection((s) => s.ringId);
  const setRing = useSelection((s) => s.setRing);
  const { data, isLoading, isError } = useQuery({
    queryKey: queryKeys.rings(sort),
    queryFn: () => api.rings(sort),
    // Keeping the previous list mounted while a re-sort loads is what stops
    // the panel blanking on every filter change.
    placeholderData: (previous) => previous,
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <div
        style={{
          height: 44,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 12px",
          borderBottom: "1px solid var(--border-subtle)",
          flexShrink: 0,
        }}
      >
        <span style={{ fontSize: 14, fontWeight: 500 }}>Candidate rings</span>
        <span className="mono" style={{ fontSize: 11, color: "var(--fg-muted)" }}>
          {data ? `${data.returned}/${data.total}` : "—"}
        </span>
      </div>

      <div
        style={{
          display: "flex",
          gap: 2,
          padding: "6px 8px",
          borderBottom: "1px solid var(--border-subtle)",
          flexShrink: 0,
        }}
      >
        {SORTS.map((option) => (
          <button
            key={option.key}
            onClick={() => onSortChange(option.key)}
            style={{
              fontSize: 11,
              padding: "3px 8px",
              borderRadius: "var(--radius-control)",
              color: sort === option.key ? "var(--accent)" : "var(--fg-muted)",
              background: sort === option.key ? "var(--accent-muted)" : "transparent",
              border: `1px solid ${sort === option.key ? "var(--accent)" : "transparent"}`,
            }}
          >
            {option.label}
          </button>
        ))}
      </div>

      <div className="scroll" style={{ flex: 1 }}>
        {isError && <StatePanel title="Could not load rings" tone="error" />}
        {isLoading && !data && (
          <div style={{ padding: 8 }}>
            {/* Skeletons occupy the exact final row height, so nothing shifts
                when the data lands. */}
            {Array.from({ length: 14 }).map((_, i) => (
              <div
                key={i}
                style={{
                  height: 34,
                  marginBottom: 1,
                  background: "var(--bg-raised)",
                  opacity: 0.35,
                  borderRadius: 2,
                }}
              />
            ))}
          </div>
        )}
        {data?.rings.map((ring) => {
          const selected = ring.ring_id === ringId;
          return (
            <button
              key={ring.ring_id}
              onClick={() => setRing(ring.ring_id)}
              style={{
                display: "grid",
                gridTemplateColumns: "3px 52px 1fr 30px 44px 42px",
                alignItems: "center",
                gap: 8,
                width: "100%",
                height: 34,
                padding: "0 10px 0 0",
                textAlign: "left",
                background: selected ? "var(--accent-muted)" : "transparent",
                borderLeft: `3px solid ${riskColor(ring.composite)}`,
                borderBottom: "1px solid var(--border-subtle)",
              }}
            >
              <span />
              <span className="mono" style={{ fontSize: 12, paddingLeft: 7 }}>
                {String(ring.ring_id).padStart(4, "0")}
              </span>
              <span
                style={{
                  fontSize: 11,
                  color: "var(--fg-secondary)",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                <span className="mono">{ring.n_clients}</span> clients ·{" "}
                <span className="mono">{ring.n_transactions}</span> txns
              </span>
              <span
                className="mono"
                title={`${ring.n_fraud_clients} of ${ring.n_clients} clients confirmed fraudulent`}
                style={{
                  fontSize: 11,
                  textAlign: "right",
                  color: ring.n_fraud_clients > 0 ? "var(--risk-4)" : "var(--fg-muted)",
                }}
              >
                {ring.n_fraud_clients > 0 ? `${ring.n_fraud_clients}f` : "—"}
              </span>
              <RiskSignature axes={ring.axes} />
              <span className="mono" style={{ fontSize: 12, textAlign: "right" }}>
                {ring.composite.toFixed(3)}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
