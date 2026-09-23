import { useQuery } from "@tanstack/react-query";
import { api, queryKeys } from "../api/client";
import { RiskSignature } from "../components/RiskSignature";
import { StatePanel } from "../components/StatePanel";
import { useSelection } from "../store/selection";
import { riskColor } from "../lib/risk";

// Every axis the API can sort by. Exposing them is the point: measurement
// showed the composite ranks below its own best component, and a reader should
// be able to see that by clicking rather than take it on trust.
const SORTS = [
  { key: "burst_share", label: "Burst" },
  { key: "composite", label: "Composite" },
  { key: "synchrony", label: "Sync" },
  { key: "density", label: "Density" },
  { key: "tightness", label: "Amount" },
  { key: "n_clients", label: "Size" },
];

const ROW_HEIGHT = 62;

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
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "16px 16px 12px",
          flexShrink: 0,
        }}
      >
        <div>
          <div style={{ fontSize: 15, fontWeight: 600, letterSpacing: "-0.02em" }}>Candidate rings</div>
          <div className="caps" style={{ marginTop: 1 }}>
            ranked by {sort.replace("_", " ")}
          </div>
        </div>
        <span
          className="mono"
          style={{
            fontSize: 11,
            color: "var(--ink-2)",
            padding: "4px 9px",
            borderRadius: 999,
            background: "var(--paper-sunken)",
          }}
        >
          {data ? `${data.returned}/${data.total}` : "—"}
        </span>
      </div>

      {/* Segmented control rather than six loose buttons: one recessed track
          with a single filled segment reads as "pick one of these", which is
          what sorting is. */}
      <div style={{ padding: "0 12px 12px", flexShrink: 0 }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 3,
            padding: 3,
            background: "var(--paper-sunken)",
            borderRadius: 10,
          }}
        >
          {SORTS.map((option) => {
            const active = sort === option.key;
            return (
              <button
                key={option.key}
                onClick={() => onSortChange(option.key)}
                aria-pressed={active}
                style={{
                  fontSize: 11.5,
                  fontWeight: active ? 600 : 500,
                  padding: "6px 4px",
                  borderRadius: 7,
                  color: active ? "var(--ink)" : "var(--ink-3)",
                  background: active ? "var(--paper-raised)" : "transparent",
                  boxShadow: active ? "var(--lift-1)" : "none",
                  transition: "background 200ms linear, color 200ms linear, box-shadow 200ms linear",
                }}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="scroll" style={{ flex: 1, padding: "0 10px 12px" }}>
        {isError && <StatePanel title="Could not load rings" tone="error" />}
        {isLoading && !data && (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {/* Skeletons occupy the exact final row height, so nothing shifts
                when the data lands. */}
            {Array.from({ length: 10 }).map((_, i) => (
              <div key={i} className="skeleton" style={{ height: ROW_HEIGHT, borderRadius: 12 }} />
            ))}
          </div>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {data?.rings.map((ring, index) => {
            const selected = ring.ring_id === ringId;
            const tint = riskColor(ring.composite);
            return (
              <button
                key={ring.ring_id}
                onClick={() => setRing(ring.ring_id)}
                aria-pressed={selected}
                style={{
                  position: "relative",
                  display: "grid",
                  gridTemplateColumns: "1fr auto",
                  rowGap: 6,
                  alignItems: "center",
                  width: "100%",
                  minHeight: ROW_HEIGHT,
                  padding: "10px 12px 10px 14px",
                  textAlign: "left",
                  borderRadius: 12,
                  background: selected ? "var(--paper-raised)" : "transparent",
                  border: `1px solid ${selected ? "var(--accent-wash-2)" : "transparent"}`,
                  boxShadow: selected ? "var(--lift-1)" : "none",
                  overflow: "hidden",
                  transition: "background 180ms linear, border-color 180ms linear, box-shadow 180ms linear",
                }}
                onMouseEnter={(e) => {
                  if (!selected) e.currentTarget.style.background = "var(--paper-sunken)";
                }}
                onMouseLeave={(e) => {
                  if (!selected) e.currentTarget.style.background = "transparent";
                }}
              >
                {/* Risk spine. It is the only place the ramp appears at full
                    size in the list, so the column scans as a risk gradient
                    from top to bottom. */}
                <span
                  aria-hidden
                  style={{
                    position: "absolute",
                    left: 0,
                    top: 8,
                    bottom: 8,
                    width: 3,
                    borderRadius: 999,
                    background: tint,
                  }}
                />

                <span style={{ display: "flex", alignItems: "baseline", gap: 8, minWidth: 0 }}>
                  <span className="mono" style={{ fontSize: 9.5, color: "var(--ink-4)", width: 16 }}>
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span className="mono" style={{ fontSize: 13.5, fontWeight: 600, letterSpacing: "-0.03em" }}>
                    {String(ring.ring_id).padStart(4, "0")}
                  </span>
                  {ring.n_fraud_clients > 0 && (
                    <span
                      className="mono"
                      title={`${ring.n_fraud_clients} of ${ring.n_clients} clients confirmed fraudulent`}
                      style={{
                        fontSize: 9.5,
                        fontWeight: 600,
                        padding: "1px 6px",
                        borderRadius: 999,
                        color: "var(--risk-4)",
                        background: "var(--risk-4-wash)",
                      }}
                    >
                      {ring.n_fraud_clients}f
                    </span>
                  )}
                </span>

                <span className="mono" style={{ fontSize: 13, fontWeight: 600, letterSpacing: "-0.03em" }}>
                  {ring.composite.toFixed(3)}
                </span>

                <span
                  style={{
                    gridColumn: "1 / 2",
                    fontSize: 11.5,
                    color: "var(--ink-2)",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    paddingLeft: 24,
                  }}
                >
                  <span className="mono" style={{ color: "var(--ink)" }}>{ring.n_clients}</span> clients ·{" "}
                  <span className="mono" style={{ color: "var(--ink)" }}>{ring.n_transactions}</span> txns ·{" "}
                  <span className="mono" style={{ color: "var(--ink)" }}>{ring.span_days}</span>d
                </span>
                <RiskSignature axes={ring.axes} width={52} height={16} />
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
