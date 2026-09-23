import { useQuery } from "@tanstack/react-query";
import { api, queryKeys } from "../api/client";
import { AXIS_ORDER, type AxisName } from "../api/types";
import { RiskSignature } from "../components/RiskSignature";
import { StatePanel } from "../components/StatePanel";
import { TemporalStrip } from "./TemporalStrip";
import { formatAmount, riskColor, truncateId } from "../lib/risk";
import { useSelection } from "../store/selection";

function Section({ title, aside, children }: { title: string; aside?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div style={{ padding: "16px 18px", borderTop: "1px solid var(--rule)" }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 12 }}>
        <span className="caps">{title}</span>
        {aside}
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
 * from a progress bar.
 */
function AxisBreakdown({ axes, raw }: { axes: Record<AxisName, number>; raw: Record<AxisName, number> }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {AXIS_ORDER.map((axis) => (
        <div key={axis} style={{ display: "grid", gridTemplateColumns: "82px minmax(0, 1fr) 48px", gap: 10, alignItems: "center" }}>
          <span style={{ fontSize: 11.5, color: "var(--ink-2)", fontWeight: 500 }}>
            {axis === "concentration" ? "concen." : axis}
          </span>
          <div style={{ position: "relative", height: 8, background: "var(--paper-sunken)", borderRadius: 999 }}>
            <div
              style={{
                width: `${axes[axis] * 100}%`,
                height: "100%",
                background: riskColor(axes[axis]),
                borderRadius: 999,
                transition: "width 320ms var(--ease-out), background 320ms linear",
              }}
            />
            {/* Population median, so the bar is read against the field. */}
            <div
              style={{
                position: "absolute",
                left: "50%",
                top: -3,
                width: 1,
                height: 14,
                background: "var(--rule-ink)",
              }}
            />
          </div>
          <span className="mono" style={{ fontSize: 11.5, textAlign: "right", color: "var(--ink-2)" }}>
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
  const setFocusedAttribute = useSelection((s) => s.setFocusedAttribute);

  const detail = useQuery({
    queryKey: queryKeys.ring(ringId ?? -1),
    queryFn: () => api.ring(ringId as number),
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
  const hours = timeline.data ? (timeline.data.t_max - timeline.data.t_min) / 3600 : null;

  return (
    <div className="scroll" style={{ height: "100%" }}>
      <div style={{ padding: "18px 18px 16px" }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 14 }}>
          <div>
            <div className="caps">flagged cluster</div>
            <div className="mono" style={{ fontSize: 24, fontWeight: 600, letterSpacing: "-0.04em", marginTop: 2 }}>
              RING-{String(ring.ring_id).padStart(4, "0")}
            </div>
          </div>
          <RiskSignature axes={ring.axes} width={104} height={30} labels />
        </div>

        {/* A plain-English claim before any chart. Trivial to build, and it is
            what makes the panel legible in the first two seconds. */}
        <p style={{ fontSize: 13, color: "var(--ink-2)", margin: "14px 0 0", lineHeight: 1.65 }}>
          <span className="mono" style={{ color: "var(--ink)" }}>{ring.n_clients}</span> clients sharing{" "}
          <span className="mono" style={{ color: "var(--ink)" }}>{ring.n_shared_attributes}</span> attributes,{" "}
          <span className="mono" style={{ color: "var(--ink)" }}>{ring.n_transactions}</span> transactions
          {hours !== null && (
            <>
              {" "}
              across{" "}
              <span className="mono" style={{ color: "var(--ink)" }}>
                {hours < 48 ? `${hours.toFixed(1)}h` : `${ring.span_days}d`}
              </span>
            </>
          )}
          .
          {ring.n_fraud_clients > 0 && (
            <span style={{ color: "var(--risk-4)", fontWeight: 500 }}>
              {" "}
              {ring.n_fraud_clients} of {ring.n_clients} confirmed fraudulent.
            </span>
          )}
        </p>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: 1,
            marginTop: 16,
            background: "var(--rule)",
            border: "1px solid var(--rule)",
            borderRadius: 12,
            overflow: "hidden",
          }}
        >
          {[
            ["clients", String(ring.n_clients)],
            ["txns", String(ring.n_transactions)],
            ["amount", formatAmount(ring.total_amount)],
            ["score", ring.composite.toFixed(3)],
          ].map(([label, value]) => (
            <div key={label} style={{ background: "var(--paper-raised)", padding: "9px 10px" }}>
              <div className="caps" style={{ fontSize: 9 }}>
                {label}
              </div>
              <div className="mono" style={{ fontSize: 15, fontWeight: 600, letterSpacing: "-0.03em", marginTop: 1 }}>
                {value}
              </div>
            </div>
          ))}
        </div>
      </div>

      <Section title="Risk basis" aside={<span style={{ fontSize: 10, color: "var(--ink-4)" }}>tick = median ring</span>}>
        <AxisBreakdown axes={ring.axes} raw={ring.raw} />
      </Section>

      <Section
        title="What links them"
        aside={
          ring.shared_attributes.length < ring.n_shared_attributes ? (
            <span className="mono" style={{ fontSize: 10, color: "var(--ink-4)" }}>
              {Math.min(10, ring.shared_attributes.length)} of {ring.n_shared_attributes}
            </span>
          ) : undefined
        }
      >
        <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
          {ring.shared_attributes.slice(0, 10).map((attribute) => {
            const active = focusedAttribute === attribute.id;
            return (
              <button
                key={attribute.id}
                onClick={() => setFocusedAttribute(active ? null : attribute.id)}
                title="Dim everything on the canvas except this attribute"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  fontSize: 11,
                  padding: "4px 5px 4px 9px",
                  borderRadius: 999,
                  background: active ? "var(--accent-wash)" : "var(--paper-raised)",
                  border: `1px solid ${active ? "var(--accent)" : "var(--rule)"}`,
                  transition: "background 180ms linear, border-color 180ms linear",
                }}
              >
                <span style={{ color: "var(--ink-3)" }}>{attribute.type}</span>
                <span className="mono" style={{ color: "var(--ink)" }}>{attribute.value.slice(0, 16)}</span>
                <span
                  className="mono"
                  style={{
                    fontSize: 10,
                    fontWeight: 600,
                    padding: "1px 6px",
                    borderRadius: 999,
                    color: active ? "var(--paper-raised)" : "var(--accent)",
                    background: active ? "var(--accent)" : "var(--accent-wash)",
                  }}
                >
                  ×{attribute.n_clients}
                </span>
              </button>
            );
          })}
        </div>
      </Section>

      <Section title="Timing" aside={<span style={{ fontSize: 10, color: "var(--ink-4)" }}>one lane per client</span>}>
        {timeline.isError ? (
          <div style={{ fontSize: 11.5, color: "var(--ink-3)", height: 120 }}>Timeline unavailable.</div>
        ) : timeline.data ? (
          <TemporalStrip data={timeline.data} />
        ) : (
          <div className="skeleton" style={{ height: 120, borderRadius: 8 }} />
        )}
      </Section>

      <Section title={`Members · ${ring.members.length}`}>
        <div style={{ display: "flex", flexDirection: "column" }}>
          {ring.members.map((member) => (
            <div
              key={member.id}
              style={{
                display: "grid",
                gridTemplateColumns: "4px minmax(0, 1fr) 34px 60px",
                gap: 9,
                alignItems: "center",
                height: 28,
                fontSize: 11.5,
                borderBottom: "1px solid var(--rule)",
              }}
            >
              <span
                title={member.is_fraud ? "confirmed fraudulent" : "no label"}
                style={{
                  height: 14,
                  borderRadius: 999,
                  background: member.is_fraud ? "var(--risk-4)" : "var(--rule-strong)",
                }}
              />
              <span className="mono" style={{ color: "var(--ink-2)" }}>{truncateId(member.uid)}</span>
              <span className="mono" style={{ textAlign: "right", color: "var(--ink-3)" }}>{member.n_transactions}</span>
              <span className="mono" style={{ textAlign: "right" }}>{formatAmount(member.total_amount)}</span>
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}
