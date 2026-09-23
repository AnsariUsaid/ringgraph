import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, queryKeys } from "../api/client";
import { StatePanel } from "../components/StatePanel";

const STRATUM_LABELS: Record<string, string> = {
  full_test: "All test transactions",
  has_snapshot: "Rows with graph history",
  linked_clients: "Clients with links",
};

/** The headline result, reported as it came out.
 *
 * This panel shows a null, and shows it honestly. The multi-seed spread is
 * drawn because on this problem seed-only variation exceeds every model
 * difference measured -- a bar chart of two point estimates would imply a
 * precision the experiment does not have.
 */
export function ModelComparison() {
  const [threshold, setThreshold] = useState(0.99);
  const models = useQuery({ queryKey: queryKeys.models(), queryFn: api.models });
  const axes = useQuery({ queryKey: queryKeys.axes(), queryFn: api.axes });
  const sweep = useQuery({ queryKey: queryKeys.sweep("m1_tuned"), queryFn: () => api.sweep("m1_tuned") });

  // The whole sweep arrives in one response, so dragging the slider is an
  // array lookup rather than a request per frame (D-25).
  const operating = useMemo(() => {
    if (!sweep.data) return null;
    const points = sweep.data.sweep;
    const index = Math.min(points.length - 1, Math.round(threshold * (points.length - 1)));
    return points[index];
  }, [sweep.data, threshold]);

  if (models.isError) return <StatePanel title="Could not load model metrics" tone="error" />;
  if (!models.data) {
    return <StatePanel title="Loading comparison…" body="Reading multi-seed results and the threshold sweep." />;
  }

  return (
    <div className="scroll" style={{ height: "100%", padding: 12 }}>
      <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 2 }}>Does structure add lift?</div>
      <div style={{ fontSize: 11, color: "var(--fg-muted)", marginBottom: 12 }}>
        TPR at 1% false-positive rate · 5 seeds per model · paired on training randomness
      </div>

      {models.data && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 14 }}>
          {Object.entries(models.data.structural).map(([stratum, result]) => {
            const noise = result.sd_diff;
            const scale = 0.06;
            const centre = 50;
            const toPct = (value: number) => centre + (value / scale) * 50;
            return (
              <div key={stratum}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
                  <span style={{ color: "var(--fg-secondary)" }}>{STRATUM_LABELS[stratum] ?? stratum}</span>
                  <span className="mono" style={{ color: "var(--fg-muted)" }}>
                    {result.mean_diff >= 0 ? "+" : ""}
                    {result.mean_diff.toFixed(4)} · {result.wins}/{result.n_seeds} seeds
                  </span>
                </div>
                <div
                  style={{
                    position: "relative",
                    height: 20,
                    background: "var(--bg-sunken)",
                    borderRadius: 3,
                    marginTop: 3,
                  }}
                >
                  {/* Zero line: the reference the difference is judged against. */}
                  <div
                    style={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: 1, background: "var(--border-strong)" }}
                  />
                  {/* +/- 1 sd of the paired difference. */}
                  <div
                    style={{
                      position: "absolute",
                      left: `${Math.max(0, toPct(result.mean_diff - noise))}%`,
                      width: `${Math.min(100, (2 * noise / scale) * 50)}%`,
                      top: 6,
                      height: 8,
                      background: "var(--risk-1)",
                      opacity: 0.35,
                      borderRadius: 2,
                    }}
                  />
                  <div
                    style={{
                      position: "absolute",
                      left: `${Math.max(0, Math.min(100, toPct(result.mean_diff)))}%`,
                      top: 3,
                      width: 2,
                      height: 14,
                      background: "var(--fg-primary)",
                    }}
                  />
                </div>
              </div>
            );
          })}
          <div style={{ fontSize: 11, color: "var(--fg-muted)", lineHeight: 1.6 }}>
            {(() => {
              // Derived, not asserted. This panel's whole claim is that it
              // reports the result as it came out, so the sentence has to
              // follow the data rather than restate what it happened to be.
              const results = Object.values(models.data.structural);
              const spanning = results.filter(
                (r) => Math.abs(r.mean_diff) < r.sd_diff / Math.sqrt(r.n_seeds) * 2.776,
              ).length;
              return spanning === results.length
                ? "Every interval spans zero."
                : `${spanning} of ${results.length} intervals span zero.`;
            })()}{" "}
            {models.data.seed_note}
          </div>
        </div>
      )}

      {axes.isError && (
        <div style={{ fontSize: 11, color: "var(--fg-muted)", marginBottom: 14 }}>
          Axis metrics unavailable.
        </div>
      )}
      {axes.data && (
        <>
          <div className="caps" style={{ marginBottom: 2 }}>
            Ring-ranking power by axis
          </div>
          <div style={{ fontSize: 11, color: "var(--fg-muted)", marginBottom: 6, lineHeight: 1.5 }}>
            Fraud clients found in the top {axes.data.k} rings, over the number expected from ring
            size alone. A ranking that only sorts by size scores 1.00×.
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 3, marginBottom: 14 }}>
            {Object.entries(axes.data.axes)
              .sort((a, b) => b[1].enrichment - a[1].enrichment)
              .map(([axis, value]) => (
                <div key={axis} style={{ display: "grid", gridTemplateColumns: "96px 1fr 42px", gap: 8, alignItems: "center", fontSize: 11 }}>
                  <span style={{ color: "var(--fg-secondary)" }}>{axis}</span>
                  <div style={{ position: "relative", height: 5, background: "var(--bg-sunken)", borderRadius: 3 }}>
                    <div style={{ position: "absolute", left: "50%", top: -2, width: 1, height: 9, background: "var(--border-strong)" }} />
                    <div
                      style={{
                        width: `${Math.min(100, (value.enrichment / 2) * 100)}%`,
                        height: "100%",
                        borderRadius: 3,
                        background: value.enrichment >= 1 ? "var(--risk-2)" : "var(--risk-0)",
                      }}
                    />
                  </div>
                  <span
                    className="mono"
                    style={{ textAlign: "right", color: value.enrichment >= 1 ? "var(--fg-primary)" : "var(--fg-muted)" }}
                  >
                    {value.enrichment.toFixed(2)}×
                  </span>
                </div>
              ))}
          </div>
        </>
      )}

      {sweep.isError && (
        <div style={{ fontSize: 11, color: "var(--fg-muted)" }}>
          Threshold sweep unavailable — no prediction table for this model.
        </div>
      )}
      {operating && sweep.data && (
        <>
          <div className="caps" style={{ marginBottom: 6 }}>
            Operating point · M1 tuned
          </div>
          <input
            type="range"
            min={0}
            max={1}
            step={0.002}
            value={threshold}
            onChange={(event) => setThreshold(Number(event.target.value))}
            style={{ width: "100%", accentColor: "var(--accent)" }}
            aria-label="Decision threshold"
          />
          <div style={{ display: "flex", gap: 14, marginTop: 8 }}>
            {[
              ["caught", operating.tp, "var(--risk-2)"],
              ["missed", operating.fn, "var(--fg-muted)"],
              ["false alarms", operating.fp, "var(--risk-3)"],
              ["FPR", `${(operating.fpr * 100).toFixed(2)}%`, "var(--fg-secondary)"],
            ].map(([label, value, colour]) => (
              <div key={label as string}>
                <div className="caps" style={{ marginBottom: 1 }}>
                  {label}
                </div>
                <div className="mono" style={{ fontSize: 15, color: colour as string }}>
                  {typeof value === "number" ? value.toLocaleString() : value}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
