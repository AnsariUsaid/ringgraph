import { useQuery } from "@tanstack/react-query";
import { api, queryKeys } from "../api/client";
import { AXIS_ORDER, type AxisName } from "../api/types";
import { RiskSignature } from "../components/RiskSignature";
import { StatePanel } from "../components/StatePanel";
import { NodeDetail } from "./NodeDetail";
import { TemporalStrip } from "./TemporalStrip";
import { formatAmount, riskColor, truncateId } from "../lib/risk";
import { useSelection } from "../store/selection";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ padding: "12px", borderBottom: "1px solid var(--border-subtle)" }}>
      <div className="caps" style={{ marginBottom: 8 }}>
        {title}
      </div>
      {children}
    </div>
  );
}

/** Horizontal axis bars with the population median marked on the track.
 *
 * Not a radar chart: four axes make radar unreadable, area encodes
 * misleadingly, and it is the clearest "reached for a chart library" tell.
 * The median tick is what turns "0.82" into "0.82, far above typical" -- the
 * comparison a reader actually needs, and what separates a statistical graphic
 * from a progress bar (D-32).
 */
function AxisBreakdown({ axes, raw }: { axes: Record<AxisName, number>; raw: Record<AxisName, number> }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
      {AXIS_ORDER.map((axis) => (
        <div key={axis} style={{ display: "grid", gridTemplateColumns: "96px 1fr 46px", gap: 8, alignItems: "center" }}>
          <span className="caps" style={{ marginBottom: 0, letterSpacing: "0.03em" }}>
            {axis === "concentration" ? "concen." : axis}
          </span>
          <div style={{ position: "relative", height: 6, background: "var(--bg-sunken)", borderRadius: 3 }}>
            <div
              style={{
                width: `${axes[axis] * 100}%`,
                height: "100%",
                background: riskColor(axes[axis]),
                borderRadius: 3,
                transition: "width 220ms cubic-bezier(.2,0,0,1)",
              }}
            />
            {/* Population median, so the bar is read against the field. */}
            <div
              style={{
                position: "absolute",
                left: "50%",
                top: -2,
                width: 1,
                height: 10,
                background: "var(--fg-muted)",
                opacity: 0.7,
              }}
            />
          </div>
          <span className="mono" style={{ fontSize: 11, textAlign: "right", color: "var(--fg-secondary)" }}>
            {raw[axis] >= 100 ? raw[axis].toFixed(0) : raw[axis].toFixed(2)}
          </span>
        </div>
      ))}
    </div>
  );
}

export function EvidencePanel() {
  const ringId = useSelection((s) => s.ringId);
  const focusedAttribute = useSelection((s) => s.focusedAttribute);
  const selectedNodeId = useSelection((s) => s.selectedNodeId);
  const setFocusedAttribute = useSelection((s) => s.setFocusedAttribute);

  const detail = useQuery({
    queryKey: queryKeys.ring(ringId ?? -1),
    queryFn: () => api.ring(ringId as number),
    enabled: ringId !== null,
  });
  const subgraph = useQuery({
    queryKey: queryKeys.subgraph(ringId ?? -1),
    queryFn: () => api.subgraph(ringId as number),
    enabled: ringId !== null,
  });
  const timeline = useQuery({
    queryKey: queryKeys.timeline(ringId ?? -1),
    queryFn: () => api.timeline(ringId as number),
    enabled: ringId !== null,
  });

  if (ringId === null) {
    return <StatePanel title="No ring selected" body="Evidence for a flagged cluster appears here." />;
  }
  if (detail.isError) return <StatePanel title="Could not load evidence" tone="error" />;
  if (!detail.data) return <StatePanel title="Loading evidence…" />;

  const ring = detail.data;
  const spanSeconds = timeline.data ? timeline.data.t_max - timeline.data.t_min : null;

  return (
    <div className="scroll" style={{ height: "100%" }}>
      {selectedNodeId && subgraph.data && (
        <NodeDetail nodeId={selectedNodeId} ring={ring} elements={subgraph.data.elements} />
      )}
      <div style={{ padding: "12px", borderBottom: "1px solid var(--border-subtle)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span className="mono" style={{ fontSize: 20, fontWeight: 600 }}>
            RING-{String(ring.ring_id).padStart(4, "0")}
          </span>
          <RiskSignature axes={ring.axes} width={96} height={22} labels />
        </div>

        {/* A plain-English claim before any chart. Trivial to build, and it is
            what makes the panel legible in the first two seconds. */}
        <div style={{ fontSize: 12, color: "var(--fg-secondary)", marginTop: 8, lineHeight: 1.6 }}>
          <span className="mono">{ring.n_clients}</span> clients sharing{" "}
          <span className="mono">{ring.n_shared_attributes}</span> attributes,{" "}
          <span className="mono">{ring.n_transactions}</span> transactions
          {spanSeconds !== null && (
            <>
              {" "}
              across{" "}
              <span className="mono">
                {spanSeconds < 3600
                  ? `${Math.max(1, Math.round(spanSeconds / 60))} min`
                  : spanSeconds < 48 * 3600
                    ? `${(spanSeconds / 3600).toFixed(1)}h`
                    : `${ring.span_days}d`}
              </span>
            </>
          )}
          .
          {ring.n_fraud_clients > 0 && (
            <span style={{ color: "var(--risk-4)" }}>
              {" "}
              {ring.n_fraud_clients} of {ring.n_clients} confirmed fraudulent.
            </span>
          )}
        </div>

        <div style={{ display: "flex", gap: 18, marginTop: 10 }}>
          {[
            ["clients", ring.n_clients],
            ["txns", ring.n_transactions],
            ["amount", formatAmount(ring.total_amount)],
            ["score", ring.composite.toFixed(3)],
          ].map(([label, value]) => (
            <div key={label as string}>
              <div className="caps" style={{ marginBottom: 1 }}>
                {label}
              </div>
              <div className="mono" style={{ fontSize: 15 }}>
                {value}
              </div>
            </div>
          ))}
        </div>
      </div>

      <Section title="Risk basis">
        <AxisBreakdown axes={ring.axes} raw={ring.raw} />
      </Section>

      <Section title="What links them">
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {ring.shared_attributes.length < ring.n_shared_attributes && (
            <span style={{ fontSize: 11, color: "var(--fg-muted)", alignSelf: "center" }}>
              showing {Math.min(10, ring.shared_attributes.length)} of {ring.n_shared_attributes}
            </span>
          )}
          {ring.shared_attributes.slice(0, 10).map((attribute) => {
            const active = focusedAttribute === attribute.id;
            return (
              <button
                key={attribute.id}
                onClick={() => setFocusedAttribute(active ? null : attribute.id)}
                title="Dim everything on the canvas except this attribute"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 5,
                  fontSize: 11,
                  padding: "3px 7px",
                  borderRadius: "var(--radius-chip)",
                  background: active ? "var(--accent-muted)" : "var(--bg-raised)",
                  border: `1px solid ${active ? "var(--accent)" : "var(--border-default)"}`,
                }}
              >
                <span style={{ color: "var(--fg-muted)" }}>{attribute.type}</span>
                <span className="mono">{attribute.value.slice(0, 18)}</span>
                <span className="mono" style={{ color: "var(--accent)" }}>
                  ×{attribute.n_clients}
                </span>
              </button>
            );
          })}
        </div>
      </Section>

      <Section title="Timing">
        {timeline.isError ? (
          <div style={{ fontSize: 11, color: "var(--fg-muted)", height: 120 }}>
            Timeline unavailable.
          </div>
        ) : timeline.data ? (
          <TemporalStrip data={timeline.data} />
        ) : (
          <div style={{ height: 120 }} />
        )}
      </Section>

      <Section title={`Members (${ring.members.length})`}>
        <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
          {ring.members.map((member) => (
            <div
              key={member.id}
              style={{
                display: "grid",
                gridTemplateColumns: "3px 1fr 34px 56px",
                gap: 7,
                alignItems: "center",
                height: 26,
                fontSize: 11,
              }}
            >
              <span
                style={{
                  height: 16,
                  background: member.is_fraud ? "var(--risk-4)" : "var(--risk-0)",
                  borderRadius: 1,
                }}
              />
              <span className="mono" style={{ color: "var(--fg-secondary)" }}>
                {truncateId(member.uid)}
              </span>
              <span className="mono" style={{ textAlign: "right", color: "var(--fg-muted)" }}>
                {member.n_transactions}
              </span>
              <span className="mono" style={{ textAlign: "right" }}>
                {formatAmount(member.total_amount)}
              </span>
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}
