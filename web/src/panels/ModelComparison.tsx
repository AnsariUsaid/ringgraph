import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, queryKeys } from "../api/client";
import { StatePanel } from "../components/StatePanel";
import type { StratumResult } from "../api/types";

const STRATA: Record<string, { label: string; note: string }> = {
  full_test: {
    label: "All test transactions",
    note: "89,326 rows · structural features are non-trivial on about 1% of them",
  },
  has_snapshot: {
    label: "Rows with graph history",
    note: "45,845 rows · a snapshot existed before the transaction",
  },
  linked_clients: {
    label: "Clients with links",
    note: "2,208 rows · the population the structural features exist for",
  },
};

const T_CRIT = 2.776; // two-sided 95%, 4 degrees of freedom at 5 seeds

function Section({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <section style={{ marginBottom: 56 }}>
      <h2 style={{ fontSize: 19, fontWeight: 600, margin: 0, letterSpacing: "-0.01em" }}>{title}</h2>
      {sub && (
        <p style={{ fontSize: 13.5, color: "var(--fg-secondary)", lineHeight: 1.65, margin: "7px 0 22px", maxWidth: 760 }}>
          {sub}
        </p>
      )}
      {children}
    </section>
  );
}

/** One stratum: the paired difference, its interval, and the zero line.
 *
 * Drawn as an interval rather than two bars because the point of the result is
 * that the difference cannot be distinguished from zero. Two bars would imply a
 * precision this experiment does not have.
 */
function DifferenceRow({ stratum, result }: { stratum: string; result: StratumResult }) {
  const se = result.sd_diff / Math.sqrt(result.n_seeds);
  const half = T_CRIT * se;
  const scale = 0.18; // full width spans -0.09..+0.09 TPR
  const pct = (v: number) => 50 + (v / scale) * 100;
  const meta = STRATA[stratum] ?? { label: stratum, note: "" };
  const spansZero = Math.abs(result.mean_diff) < half;

  return (
    <div style={{ marginBottom: 30 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 20 }}>
        <div>
          <div style={{ fontSize: 15, fontWeight: 500 }}>{meta.label}</div>
          <div style={{ fontSize: 12, color: "var(--fg-muted)", marginTop: 2 }}>{meta.note}</div>
        </div>
        <div style={{ textAlign: "right", flexShrink: 0 }}>
          <div className="mono" style={{ fontSize: 22, fontWeight: 600 }}>
            {result.mean_diff >= 0 ? "+" : ""}
            {result.mean_diff.toFixed(4)}
          </div>
          <div className="mono" style={{ fontSize: 11.5, color: "var(--fg-muted)" }}>
            {result.wins}/{result.n_seeds} seeds favour M2
          </div>
        </div>
      </div>

      <div style={{ position: "relative", height: 40, marginTop: 12 }}>
        <div style={{ position: "absolute", inset: "16px 0 16px 0", background: "var(--bg-sunken)", borderRadius: 4 }} />
        {/* Zero: the reference the whole claim turns on. */}
        <div style={{ position: "absolute", left: "50%", top: 4, bottom: 4, width: 1, background: "var(--border-strong)" }} />
        <div
          style={{
            position: "absolute",
            left: `${Math.max(0, pct(result.mean_diff - half))}%`,
            width: `${Math.min(100, (2 * half / scale) * 100)}%`,
            top: 14,
            height: 12,
            background: spansZero ? "var(--risk-1)" : "var(--risk-3)",
            opacity: 0.38,
            borderRadius: 3,
            transition: "all var(--dur-slow) var(--ease-out)",
          }}
        />
        <div
          style={{
            position: "absolute",
            left: `${Math.max(0, Math.min(100, pct(result.mean_diff)))}%`,
            top: 10,
            width: 2.5,
            height: 20,
            background: "var(--fg-primary)",
            borderRadius: 2,
          }}
        />
      </div>
      <div className="mono" style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--fg-muted)" }}>
        <span>−0.09</span>
        <span>
          95% CI [{(result.mean_diff - half).toFixed(4)}, {(result.mean_diff + half).toFixed(4)}]
        </span>
        <span>+0.09</span>
      </div>
    </div>
  );
}

export function ModelComparison() {
  const [threshold, setThreshold] = useState(0.99);
  const models = useQuery({ queryKey: queryKeys.models(), queryFn: api.models });
  const axes = useQuery({ queryKey: queryKeys.axes(), queryFn: api.axes });
  const sweep = useQuery({ queryKey: queryKeys.sweep("m1_tuned"), queryFn: () => api.sweep("m1_tuned") });

  // The whole sweep arrives in one response, so dragging is an array lookup
  // rather than a request per frame (D-25).
  const operating = useMemo(() => {
    if (!sweep.data) return null;
    const points = sweep.data.sweep;
    return points[Math.min(points.length - 1, Math.round(threshold * (points.length - 1)))];
  }, [sweep.data, threshold]);

  if (models.isError) return <StatePanel title="Could not load model metrics" tone="error" />;
  if (!models.data) return <StatePanel title="Loading results…" />;

  const results = Object.entries(models.data.structural);
  const spanning = results.filter(([, r]) => Math.abs(r.mean_diff) < (T_CRIT * r.sd_diff) / Math.sqrt(r.n_seeds)).length;
  const widest = Math.max(...results.map(([, r]) => (T_CRIT * r.sd_diff) / Math.sqrt(r.n_seeds)));

  return (
    <div style={{ padding: "108px clamp(24px, 7vw, 120px) 110px", maxWidth: 1180 }}>
      <div className="rise rise-1 caps" style={{ color: "var(--accent)", marginBottom: 14 }}>
        the headline result
      </div>
      <h1 className="rise rise-1" style={{ fontSize: "clamp(30px, 3.6vw, 44px)", fontWeight: 600, letterSpacing: "-0.025em", lineHeight: 1.1, margin: 0 }}>
        Does graph structure add predictive lift?
      </h1>
      <p className="rise rise-2" style={{ fontSize: 15.5, color: "var(--fg-secondary)", lineHeight: 1.7, maxWidth: 730, marginTop: 18 }}>
        M1 is a tuned LightGBM over tabular features, <em>including</em> the device columns — so any
        gap measures structure rather than categorical encoding. M2 adds snapshot-based graph
        features. Both are tuned on their own feature sets with the same search space and budget,
        and trained across five seeds they share, so a difference reflects the features and not the
        randomness.
      </p>

      <div className="rise rise-3" style={{ display: "flex", gap: 34, margin: "30px 0 52px", flexWrap: "wrap" }}>
        {[
          ["metric", "TPR at 1% FPR"],
          ["test period", "days 151–181"],
          ["seeds", "5, paired"],
          ["intervals spanning zero", `${spanning} of ${results.length}`],
        ].map(([label, value]) => (
          <div key={label}>
            <div className="caps" style={{ marginBottom: 3 }}>{label}</div>
            <div className="mono" style={{ fontSize: 16 }}>{value}</div>
          </div>
        ))}
      </div>

      <Section title="M2 − M1, by population">
        <div className="rise rise-3">
          {results.map(([stratum, result]) => (
            <DifferenceRow key={stratum} stratum={stratum} result={result} />
          ))}
        </div>
        <div style={{ fontSize: 13.5, color: "var(--fg-secondary)", lineHeight: 1.7, maxWidth: 760, padding: 18, borderRadius: 8, background: "var(--bg-panel)", border: "1px solid var(--border-subtle)" }}>
          {spanning === results.length ? "Every interval spans zero." : `${spanning} of ${results.length} intervals span zero.`}{" "}
          That means no difference was detected — not that none exists. The widest interval here is
          ±{widest.toFixed(3)}, so an effect smaller than roughly {(widest * 100).toFixed(0)} TPR
          points would have produced these numbers either way. {models.data.seed_note}
        </div>
      </Section>

      {axes.data && (
        <Section
          title="Which ring-scoring axis actually works"
          sub="Fraud clients found in the top 50 rings, over the number expected from ring size alone. A ranking that merely sorts by size scores 1.00×. Two of the plan's four designed axes fall below chance."
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 11 }}>
            {Object.entries(axes.data.axes)
              .sort((a, b) => b[1].enrichment - a[1].enrichment)
              .map(([axis, value], i) => (
                <div key={axis} className={`rise rise-${Math.min(6, i + 1)}`} style={{ display: "grid", gridTemplateColumns: "150px minmax(0, 1fr) 70px", gap: 16, alignItems: "center" }}>
                  <span style={{ fontSize: 13.5, color: value.enrichment >= 1.3 ? "var(--fg-primary)" : "var(--fg-secondary)" }}>{axis}</span>
                  <div style={{ position: "relative", height: 10, background: "var(--bg-sunken)", borderRadius: 5 }}>
                    <div style={{ position: "absolute", left: "50%", top: -3, width: 1, height: 16, background: "var(--border-strong)" }} />
                    <div
                      style={{
                        width: `${Math.min(100, (value.enrichment / 2) * 100)}%`,
                        height: "100%",
                        borderRadius: 5,
                        background: value.enrichment >= 1.3 ? "var(--risk-2)" : value.enrichment >= 1 ? "var(--risk-1)" : "var(--risk-0)",
                        transition: "width var(--dur-slow) var(--ease-out)",
                      }}
                    />
                  </div>
                  <span className="mono" style={{ fontSize: 15, textAlign: "right", color: value.enrichment >= 1.3 ? "var(--fg-primary)" : "var(--fg-muted)" }}>
                    {value.enrichment.toFixed(2)}×
                  </span>
                </div>
              ))}
          </div>
          <div className="mono" style={{ fontSize: 11, color: "var(--fg-muted)", marginTop: 10, paddingLeft: 166 }}>
            the tick marks 1.00× — no better than ranking by size
          </div>
        </Section>
      )}

      {operating && sweep.data && (
        <Section title="M1 operating point" sub="Drag to trade false alarms against fraud caught. The whole curve is fetched once, so this never touches the network.">
          <input
            type="range"
            min={0}
            max={1}
            step={0.002}
            value={threshold}
            onChange={(e) => setThreshold(Number(e.target.value))}
            style={{ width: "100%", maxWidth: 760, accentColor: "var(--accent)" }}
            aria-label="Decision threshold"
          />
          <div style={{ display: "flex", gap: 46, marginTop: 20, flexWrap: "wrap" }}>
            {[
              ["fraud caught", operating.tp.toLocaleString(), "var(--risk-2)"],
              ["missed", operating.fn.toLocaleString(), "var(--fg-secondary)"],
              ["false alarms", operating.fp.toLocaleString(), "var(--risk-3)"],
              ["false-positive rate", `${(operating.fpr * 100).toFixed(2)}%`, "var(--fg-primary)"],
              ["precision", `${(operating.precision * 100).toFixed(1)}%`, "var(--fg-primary)"],
            ].map(([label, value, colour]) => (
              <div key={label}>
                <div className="caps" style={{ marginBottom: 4 }}>{label}</div>
                <div className="mono" style={{ fontSize: 28, fontWeight: 600, color: colour }}>{value}</div>
              </div>
            ))}
          </div>
        </Section>
      )}
      {sweep.isError && (
        <div style={{ fontSize: 13, color: "var(--fg-muted)" }}>
          Threshold sweep unavailable — no prediction table for this model.
        </div>
      )}
    </div>
  );
}
