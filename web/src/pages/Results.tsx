import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, queryKeys } from "../api/client";
import { StatePanel } from "../components/StatePanel";
import { Reveal } from "../components/Reveal";
import { CountUp } from "../components/CountUp";

const STRATUM_LABELS: Record<string, string> = {
  full_test: "All test transactions",
  has_snapshot: "Rows with graph history",
  linked_clients: "Clients with links",
};

const AXIS_BLURB: Record<string, string> = {
  burst_share: "share of a ring's transactions inside one burst",
  n_clients: "ring size alone",
  composite: "the four axes averaged",
  synchrony: "same-window transacting",
  tightness: "repeated amounts",
  density: "completeness of the client-to-client graph",
  concentration: "how few attributes carry the group",
};

/** Decision thresholds on this model span eight orders of magnitude -- a 3.5%
 *  fraud rate puts almost every predicted probability near zero -- so a fixed
 *  three decimals rendered most of the slider's travel as a motionless
 *  "0.000". Significant figures instead, which keeps the readout changing as
 *  the handle moves. */
function formatThreshold(value: number): string {
  if (value === 0) return "0";
  if (value >= 0.01) return value.toFixed(3);
  return value.toPrecision(3);
}

/** Numbered section head, matching the landing page's rhythm. Four identically
 *  padded cards in a column gave the page no shape at all; numbering the
 *  sections and varying what sits under each one is most of the fix. */
function Head({ index, title, blurb }: { index: string; title: React.ReactNode; blurb?: string }) {
  return (
    <Reveal style={{ marginBottom: 28 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 14, marginBottom: 10 }}>
        <span className="mono" style={{ fontSize: 11, color: "var(--accent)", fontWeight: 600 }}>
          {index}
        </span>
        <span style={{ flex: 1, height: 1, background: "var(--rule)" }} />
      </div>
      <h2 className="display" style={{ fontSize: "clamp(26px, 4vw, 42px)", margin: 0, maxWidth: 720 }}>
        {title}
      </h2>
      {blurb && (
        <p style={{ margin: "12px 0 0", maxWidth: 640, fontSize: 14.5, color: "var(--ink-2)", lineHeight: 1.68 }}>
          {blurb}
        </p>
      )}
    </Reveal>
  );
}

export function Results() {
  const [threshold, setThreshold] = useState(0.25);
  const models = useQuery({ queryKey: queryKeys.models(), queryFn: api.models });
  const axes = useQuery({ queryKey: queryKeys.axes(), queryFn: api.axes });
  const sweep = useQuery({ queryKey: queryKeys.sweep("m1_tuned"), queryFn: () => api.sweep("m1_tuned") });

  // The whole sweep arrives in one response, so dragging the slider is an
  // array lookup rather than a request per frame.
  const operating = useMemo(() => {
    if (!sweep.data) return null;
    const points = sweep.data.sweep;
    const index = Math.min(points.length - 1, Math.round(threshold * (points.length - 1)));
    return points[index];
  }, [sweep.data, threshold]);

  // Recharts redraws every point it is handed; 400 of them at 1px apart is
  // invisible detail bought at a full re-render per slider frame.
  const curve = useMemo(() => {
    if (!sweep.data) return [];
    const points = sweep.data.sweep;
    const stride = Math.max(1, Math.floor(points.length / 160));
    return points.filter((_, i) => i % stride === 0).map((p) => ({ fpr: p.fpr, tpr: p.tpr }));
  }, [sweep.data]);

  // Where the ROC splits into "bought" and "given up". Everything on the chart
  // that is coloured reads this one number, so dragging the slider repaints the
  // figure rather than nudging a dot across a static picture.
  const split = operating ? Math.min(1, Math.max(0, operating.fpr)) : 0;
  const positives = operating ? operating.tp + operating.fn : 0;
  const negatives = operating ? operating.fp + operating.tn : 0;

  return (
    <div>
      <div className="page page--narrow">
        <header style={{ padding: "calc(var(--nav-height) + 56px) 0 8px" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 14, marginBottom: 14 }}>
            <span className="mono" style={{ fontSize: 11, color: "var(--accent)", fontWeight: 600 }}>
              RESULTS
            </span>
            <span style={{ flex: 1, height: 1, background: "var(--rule)" }} />
          </div>
          <h1 className="display" style={{ fontSize: "clamp(32px, 6.4vw, 72px)", margin: 0, maxWidth: 860 }}>
            What we built, and the <em>numbers</em>.
          </h1>
          <p style={{ margin: "18px 0 0", maxWidth: 640, fontSize: 16, lineHeight: 1.68, color: "var(--ink-2)" }}>
            A transaction-level fraud model, a graph of clients linked by shared attributes, and a
            catalogue of candidate rings ranked by how coordinated they look. Models are scored as
            true-positive rate at a 1% false-positive rate on the held-out test split.
          </p>
        </header>
      </div>

      {models.isError && (
        <div className="page page--narrow" style={{ paddingTop: 40 }}>
          <div className="card" style={{ height: 240 }}>
            <StatePanel title="Could not load model metrics" tone="error" />
          </div>
        </div>
      )}

      <div className="page page--narrow" style={{ paddingBottom: 110 }}>
        {/* -------------------------------------------------- headline */}
        <section style={{ padding: "56px 0 0" }}>
          <div
            className="grid-stats"
            style={{
              background: "var(--rule)",
              border: "1px solid var(--rule)",
              borderRadius: "var(--radius-panel)",
              overflow: "hidden",
            }}
          >
            {[
              { label: "test ROC-AUC", value: 0.894, decimals: 3 },
              { label: "test PR-AUC", value: 0.528, decimals: 3 },
              { label: "TPR @ 1% FPR", value: 44.2, decimals: 1, suffix: "%" },
              { label: "features", value: 431, decimals: 0 },
            ].map((stat) => (
              <div key={stat.label} style={{ background: "var(--paper-raised)", padding: "18px 16px" }}>
                <div style={{ fontSize: 26, fontWeight: 600, letterSpacing: "-0.03em" }}>
                  <CountUp to={stat.value} decimals={stat.decimals} suffix={stat.suffix ?? ""} />
                </div>
                <div className="caps" style={{ marginTop: 3 }}>
                  {stat.label}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ------------------------------------------------ what we tried */}
        <section style={{ padding: "76px 0 0" }}>
          <Head index="01" title={<>What we <em>tried</em>.</>} />
          <Reveal>
            <ol style={{ margin: 0, paddingLeft: 20, display: "flex", flexDirection: "column", gap: 12, fontSize: 14.5, lineHeight: 1.7, color: "var(--ink-2)" }}>
              <li><span style={{ color: "var(--ink)", fontWeight: 500 }}>M1 — LightGBM on transaction features.</span> Tuned with a hyperparameter search; this is the tuned model above.</li>
              <li><span style={{ color: "var(--ink)", fontWeight: 500 }}>Client graph.</span> Clients linked through shared device and browser identity attributes, loaded into Neo4j and split into communities.</li>
              <li><span style={{ color: "var(--ink)", fontWeight: 500 }}>M2 — M1 plus graph features.</span> Point-in-time graph snapshot features (degree, triangles, clustering, PageRank, component size), in two window configurations.</li>
              <li><span style={{ color: "var(--ink)", fontWeight: 500 }}>M2 plus community features.</span> Community-level aggregates added on top of the snapshot features.</li>
              <li><span style={{ color: "var(--ink)", fontWeight: 500 }}>Ring scoring.</span> Every candidate ring scored on density, synchrony, concentration, tightness and burst share, then ranked.</li>
            </ol>
          </Reveal>
        </section>

        {/* -------------------------------------------------- model scores */}
        {models.isError && (
          <div className="card" style={{ height: 240, marginTop: 40 }}>
            <StatePanel title="Could not load model metrics" tone="error" />
          </div>
        )}
        {models.data && (
          <section style={{ padding: "76px 0 0" }}>
            <Head
              index="02"
              title={<>Model <em>scores</em>.</>}
              blurb="TPR at 1% FPR, mean ± sd over five training seeds, on three slices of the test set."
            />
            <Reveal>
              <div className="card" style={{ overflow: "hidden" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13.5 }}>
                  <thead>
                    <tr style={{ textAlign: "left" }}>
                      {["Test slice", "M1", "M2 (graph)", ...(models.data.community ? ["M2 + community"] : [])].map((h) => (
                        <th key={h} className="caps" style={{ padding: "14px 18px", borderBottom: "1px solid var(--rule)", fontWeight: 500 }}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(models.data.structural).map(([stratum, r]) => {
                      const c = models.data.community?.[stratum];
                      const cell = (mean: number, sd: number) => (
                        <td className="mono" style={{ padding: "14px 18px", borderTop: "1px solid var(--rule)" }}>
                          {(mean * 100).toFixed(1)}%<span style={{ color: "var(--ink-4)" }}> ± {(sd * 100).toFixed(1)}</span>
                        </td>
                      );
                      return (
                        <tr key={stratum}>
                          <td style={{ padding: "14px 18px", borderTop: "1px solid var(--rule)", fontWeight: 500 }}>
                            {STRATUM_LABELS[stratum] ?? stratum}
                          </td>
                          {cell(r.m1_mean, r.m1_sd)}
                          {cell(r.m2_mean, r.m2_sd)}
                          {c && cell(c.m2_mean, c.m2_sd)}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Reveal>
          </section>
        )}

        {/* ------------------------------------------------------- axes */}
        {axes.data && (
          <section style={{ paddingBottom: 20 }}>
            <Head
              index="03"
              title={<>Ring <em>ranking</em>.</>}
              blurb={`Fraud clients found in the top ${axes.data.k} rings, relative to the number expected from ring size alone (1.00×). Burst share ranks best.`}
            />
            <Reveal>
              <div style={{ display: "flex", flexDirection: "column", gap: 13 }}>
                {Object.entries(axes.data.axes)
                  .sort((a, b) => b[1].enrichment - a[1].enrichment)
                  .map(([axis, value], i) => {
                    const beats = value.enrichment >= 1;
                    const best = axis === "burst_share";
                    return (
                      <div
                        key={axis}
                        style={{
                          display: "grid",
                          gridTemplateColumns: "150px minmax(0, 1fr) 62px",
                          gap: 14,
                          alignItems: "center",
                        }}
                      >
                        <div>
                          <div style={{ fontSize: 13.5, fontWeight: best ? 600 : 500, color: beats ? "var(--ink)" : "var(--ink-3)" }}>
                            {axis.replace("_", " ")}
                          </div>
                          <div style={{ fontSize: 10.5, color: "var(--ink-3)", lineHeight: 1.35 }}>{AXIS_BLURB[axis]}</div>
                        </div>
                        <div style={{ position: "relative", height: 18, background: "var(--paper-sunken)", borderRadius: 7 }}>
                          {/* The 1.00x control line. Without it every bar looks
                              like a win. */}
                          <div style={{ position: "absolute", left: "50%", top: -4, bottom: -4, width: 1, background: "var(--rule-ink)", zIndex: 1 }} />
                          <div
                            className="on-reveal-growx"
                            style={{
                              ["--i" as string]: i,
                              width: `${Math.min(100, (value.enrichment / 2) * 100)}%`,
                              height: "100%",
                              borderRadius: 7,
                              background: best ? "var(--risk-3)" : beats ? "var(--risk-1)" : "var(--risk-0)",
                            }}
                          />
                        </div>
                        <span
                          className="mono"
                          style={{ textAlign: "right", fontSize: 13.5, fontWeight: best ? 600 : 500, color: beats ? "var(--ink)" : "var(--ink-3)" }}
                        >
                          {value.enrichment.toFixed(2)}×
                        </span>
                      </div>
                    );
                  })}
              </div>
            </Reveal>
          </section>
        )}

        {/* -------------------------------------------- operating point */}
        {sweep.isError && (
          <section style={{ padding: "76px 0 0" }}>
            <Head index="04" title={<>Pick an <em>operating point</em>.</>} blurb="No prediction table for this model — the threshold sweep is unavailable." />
          </section>
        )}

        {operating && sweep.data && (
          <section style={{ padding: "76px 0 0" }}>
            <Head
              index="04"
              title={<>Pick an <em>operating point</em>.</>}
              blurb="Drag the threshold. Everything below recolours with it: the filled region is the part of the curve you are buying, and the pale region is what you are giving up."
            />

            <Reveal>
              <div className="card" style={{ padding: "26px 26px 28px" }}>
                <div className="operating">
                  <div style={{ height: 270, margin: "0 -8px" }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={curve} margin={{ top: 6, right: 8, bottom: 2, left: -18 }}>
                        <defs>
                          {/* Two stops at the same offset is a hard edge, and
                              the offset is the live threshold -- so the figure
                              itself is the readout, not just the dot on it. */}
                          <linearGradient id="rocFill" x1="0" y1="0" x2="1" y2="0">
                            <stop offset={split} stopColor="var(--risk-3)" stopOpacity={0.38} />
                            <stop offset={split} stopColor="var(--ink-4)" stopOpacity={0.10} />
                          </linearGradient>
                          <linearGradient id="rocStroke" x1="0" y1="0" x2="1" y2="0">
                            <stop offset={split} stopColor="var(--risk-4)" />
                            <stop offset={split} stopColor="var(--ink-4)" />
                          </linearGradient>
                        </defs>
                        <CartesianGrid stroke="var(--rule)" strokeDasharray="2 4" vertical={false} />
                        <XAxis
                          dataKey="fpr"
                          type="number"
                          domain={[0, 1]}
                          tick={{ fontSize: 10, fill: "var(--ink-3)" }}
                          tickFormatter={(v: number) => v.toFixed(1)}
                          stroke="var(--rule-strong)"
                        />
                        <YAxis
                          type="number"
                          domain={[0, 1]}
                          tick={{ fontSize: 10, fill: "var(--ink-3)" }}
                          tickFormatter={(v: number) => v.toFixed(1)}
                          stroke="var(--rule-strong)"
                        />
                        <Tooltip
                          contentStyle={{
                            background: "var(--paper-raised)",
                            border: "1px solid var(--rule-strong)",
                            borderRadius: 10,
                            fontSize: 12,
                            boxShadow: "var(--lift-2)",
                          }}
                          labelFormatter={(v) => `FPR ${(Number(v) * 100).toFixed(1)}%`}
                          formatter={(v) => [`${(Number(v) * 100).toFixed(1)}%`, "TPR"] as [string, string]}
                        />
                        <ReferenceLine x={operating.fpr} stroke="var(--risk-4)" strokeDasharray="3 4" strokeWidth={1.5} />
                        <Area
                          type="monotone"
                          dataKey="tpr"
                          stroke="url(#rocStroke)"
                          strokeWidth={2.4}
                          fill="url(#rocFill)"
                          isAnimationActive={false}
                        />
                        <ReferenceDot
                          x={operating.fpr}
                          y={operating.tpr}
                          r={6.5}
                          fill="var(--risk-4)"
                          stroke="var(--paper-raised)"
                          strokeWidth={2.5}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                    <div className="caps" style={{ textAlign: "center", marginTop: -4 }}>
                      false-positive rate → true-positive rate
                    </div>
                  </div>

                  <div>
                    <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 6 }}>
                      <span className="caps">threshold</span>
                      <span className="mono" style={{ fontSize: 17, fontWeight: 600 }}>
                        {formatThreshold(operating.threshold)}
                      </span>
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={1}
                      step={0.002}
                      value={threshold}
                      onChange={(event) => setThreshold(Number(event.target.value))}
                      style={{ width: "100%", accentColor: "var(--risk-4)" }}
                      aria-label="Decision threshold"
                    />

                    {/* Two population bars that restack as the threshold moves.
                        The ROC says what the trade is in rates; this says it in
                        transactions, which is the unit the trade is actually
                        paid in. */}
                    <div style={{ marginTop: 22, display: "flex", flexDirection: "column", gap: 16 }}>
                      {[
                        {
                          label: `${positives.toLocaleString()} actual fraud`,
                          parts: [
                            { name: "caught", value: operating.tp, colour: "var(--risk-4)" },
                            { name: "missed", value: operating.fn, colour: "var(--rule-strong)" },
                          ],
                        },
                        {
                          label: `${negatives.toLocaleString()} legitimate`,
                          parts: [
                            { name: "false alarms", value: operating.fp, colour: "var(--risk-3)" },
                            { name: "cleared", value: operating.tn, colour: "var(--rule-strong)" },
                          ],
                        },
                      ].map((bar) => {
                        const total = bar.parts.reduce((sum, part) => sum + part.value, 0) || 1;
                        return (
                          <div key={bar.label}>
                            <div className="caps" style={{ marginBottom: 5 }}>
                              {bar.label}
                            </div>
                            <div style={{ display: "flex", height: 14, borderRadius: 999, overflow: "hidden", background: "var(--paper-sunken)" }}>
                              {bar.parts.map((part) => (
                                <div
                                  key={part.name}
                                  title={`${part.name}: ${part.value.toLocaleString()}`}
                                  style={{
                                    width: `${(part.value / total) * 100}%`,
                                    background: part.colour,
                                    transition: "width 160ms linear",
                                  }}
                                />
                              ))}
                            </div>
                            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 5, fontSize: 11, color: "var(--ink-2)" }}>
                              {bar.parts.map((part) => (
                                <span key={part.name} className="mono">
                                  {part.value.toLocaleString()}{" "}
                                  <span style={{ color: "var(--ink-3)" }}>{part.name}</span>
                                </span>
                              ))}
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        marginTop: 20,
                        paddingTop: 14,
                        borderTop: "1px solid var(--rule)",
                      }}
                    >
                      {[
                        ["FPR", `${(operating.fpr * 100).toFixed(2)}%`],
                        ["TPR", `${(operating.tpr * 100).toFixed(1)}%`],
                        ["precision", `${(operating.precision * 100).toFixed(1)}%`],
                      ].map(([label, value]) => (
                        <div key={label}>
                          <div className="caps" style={{ marginBottom: 2 }}>
                            {label}
                          </div>
                          <div className="mono" style={{ fontSize: 17, fontWeight: 600 }}>
                            {value}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </Reveal>
          </section>
        )}

      </div>
    </div>
  );
}
