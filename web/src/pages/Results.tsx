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
  n_clients: "ring size alone — the control, not a finding",
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

  /** Half-width of the difference axis, in TPR points. Derived from the data:
   *  these strata differ in spread by an order of magnitude, and a fixed scale
   *  clipped the widest band against both ends of its track -- which reads as
   *  a bar that ran out of room, the opposite of "this estimate is uncertain". */
  const half = useMemo(() => {
    if (!models.data) return 0.06;
    const extents = Object.values(models.data.structural).flatMap((r) => [
      Math.abs(r.mean_diff) + r.sd_diff,
      ...r.per_seed_diffs.map(Math.abs),
    ]);
    return Math.max(0.01, Math.max(...extents) * 1.12);
  }, [models.data]);

  const verdict = useMemo(() => {
    if (!models.data) return null;
    const results = Object.values(models.data.structural);
    // t(4) two-sided at 95%. Derived rather than asserted: this page's whole
    // claim is that it reports the result as it came out.
    const spanning = results.filter((r) => Math.abs(r.mean_diff) < (r.sd_diff / Math.sqrt(r.n_seeds)) * 2.776);
    return { spanning: spanning.length, total: results.length };
  }, [models.data]);

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
            Did structure add <em>lift</em>?
          </h1>
          <p style={{ margin: "18px 0 0", maxWidth: 640, fontSize: 16, lineHeight: 1.68, color: "var(--ink-2)" }}>
            Two models, identical except that the second sees graph-derived features. Five seeds each,
            paired on training randomness, scored as true-positive rate at a 1% false-positive rate.
            What follows is the answer that came out, not the one the project was hoping for.
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

      {/* ---------------------------------------------------------- verdict
          Full-bleed ink, not a card. The null is the headline of the whole
          project, and giving it the same bordered rectangle as everything else
          was the single biggest reason the page read flat. */}
      {models.data && verdict && (
        <section style={{ position: "relative", overflow: "hidden", background: "var(--ink)", color: "var(--paper)", margin: "56px 0 0" }}>
          <div
            aria-hidden
            style={{
              position: "absolute",
              inset: "-30%",
              background:
                "radial-gradient(circle at 22% 28%, rgba(95,82,232,0.40), transparent 55%), radial-gradient(circle at 80% 72%, rgba(180,29,60,0.32), transparent 55%)",
              animation: "drift 24s ease-in-out infinite",
            }}
          />
          <div className="page page--narrow" style={{ position: "relative", paddingBlock: 76 }}>
            <Reveal>
              <div className="caps" style={{ color: "rgba(255,255,255,0.5)" }}>
                Verdict
              </div>
              <h2
                className="display"
                style={{ fontSize: "clamp(38px, 7vw, 82px)", margin: "12px 0 0", color: "var(--paper)" }}
              >
                {verdict.spanning === verdict.total ? (
                  <>
                    No measurable <em style={{ color: "#a99bff" }}>difference</em>.
                  </>
                ) : (
                  <>
                    {verdict.spanning} of {verdict.total} intervals span <em style={{ color: "#a99bff" }}>zero</em>.
                  </>
                )}
              </h2>
              <p style={{ margin: "20px 0 0", maxWidth: 620, fontSize: 15, lineHeight: 1.7, color: "rgba(255,255,255,0.72)" }}>
                {models.data.seed_note}
              </p>

              <div style={{ display: "flex", flexWrap: "wrap", gap: 46, marginTop: 40 }}>
                {[
                  ["seeds per model", 5],
                  ["strata tested", verdict.total],
                  ["intervals spanning 0", verdict.spanning],
                ].map(([label, value], i) => (
                  <div key={label as string} className="on-reveal-rise" style={{ ["--i" as string]: i + 1 }}>
                    <div className="display" style={{ fontSize: 54, lineHeight: 1, color: "var(--paper)" }}>
                      <CountUp to={value as number} />
                    </div>
                    <div className="caps" style={{ marginTop: 8, color: "rgba(255,255,255,0.5)" }}>
                      {label}
                    </div>
                  </div>
                ))}
              </div>
            </Reveal>
          </div>
        </section>
      )}

      <div className="page page--narrow" style={{ paddingBottom: 110 }}>
        {/* -------------------------------------------------- paired diff */}
        {models.data && (
          <section style={{ padding: "76px 0 0" }}>
            <Head
              index="01"
              title={<>Five seeds, and they disagree with <em>each other</em>.</>}
              blurb="Tick is the mean difference, band is ±1 sd, dots are the individual seeds. The centre line is “the two models are the same”. Watch where the dots fall relative to it."
            />
            <Reveal>
              <div style={{ display: "flex", flexDirection: "column", gap: 26 }}>
                {Object.entries(models.data.structural).map(([stratum, result], row) => {
                  const toPct = (value: number) => 50 + (value / half) * 50;
                  return (
                    <div key={stratum}>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 8 }}>
                        <span style={{ color: "var(--ink)", fontWeight: 500 }}>{STRATUM_LABELS[stratum] ?? stratum}</span>
                        <span className="mono" style={{ color: "var(--ink-2)" }}>
                          {result.mean_diff >= 0 ? "+" : ""}
                          {result.mean_diff.toFixed(4)}
                          <span style={{ color: "var(--ink-4)" }}> · {result.wins}/{result.n_seeds} seeds</span>
                        </span>
                      </div>
                      <div style={{ position: "relative", height: 34, background: "var(--paper-sunken)", borderRadius: 9 }}>
                        <div style={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: 1, background: "var(--rule-ink)" }} />
                        <div
                          className="on-reveal-growc"
                          style={{
                            ["--i" as string]: row,
                            position: "absolute",
                            left: `${toPct(result.mean_diff - result.sd_diff)}%`,
                            width: `${((2 * result.sd_diff) / half) * 50}%`,
                            top: 12,
                            height: 10,
                            borderRadius: 999,
                            background: "var(--risk-1)",
                            opacity: 0.5,
                          }}
                        />
                        <div
                          className="on-reveal-pop"
                          style={{
                            ["--i" as string]: row,
                            position: "absolute",
                            left: `${toPct(result.mean_diff)}%`,
                            top: 7,
                            width: 2,
                            height: 20,
                            background: "var(--ink)",
                          }}
                        />
                        {result.per_seed_diffs.map((diff, i) => (
                          <div
                            key={i}
                            className="on-reveal-pop"
                            title={`seed ${i + 1}: ${diff >= 0 ? "+" : ""}${diff.toFixed(4)}`}
                            style={{
                              ["--i" as string]: row * 5 + i,
                              position: "absolute",
                              left: `${toPct(diff)}%`,
                              top: 22,
                              width: 7,
                              height: 7,
                              marginLeft: -3.5,
                              borderRadius: 999,
                              background: diff >= 0 ? "var(--accent-2)" : "var(--ink-3)",
                            }}
                          />
                        ))}
                      </div>
                    </div>
                  );
                })}
                <div className="mono" style={{ display: "flex", justifyContent: "space-between", fontSize: 10.5, color: "var(--ink-3)" }}>
                  <span>−{half.toFixed(2)}</span>
                  <span>0 · no difference</span>
                  <span>+{half.toFixed(2)}</span>
                </div>
              </div>
            </Reveal>
          </section>
        )}

        {/* Editorial break. Nothing here is a card, which is the point -- it
            resets the rhythm before the next dense figure. */}
        <Reveal as="section" style={{ padding: "74px 0" }}>
          <blockquote
            className="display"
            style={{
              margin: 0,
              paddingLeft: 26,
              borderLeft: "3px solid var(--risk-3)",
              fontSize: "clamp(22px, 3.2vw, 34px)",
              lineHeight: 1.28,
              maxWidth: 780,
            }}
          >
            A null is a measured bound, not a failed experiment. The structure is real — it just does
            not survive being folded into a classifier that already has the transaction's own features.
          </blockquote>
        </Reveal>

        {/* ------------------------------------------------------- axes */}
        {axes.data && (
          <section style={{ paddingBottom: 20 }}>
            <Head
              index="02"
              title={<>Where the structure <em>does</em> pay.</>}
              blurb={`Fraud clients found in the top ${axes.data.k} rings, over the number expected from ring size alone. A ranking that only sorts by size scores 1.00× — anything at or below that line is not finding structure, it is finding big clusters.`}
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
            <Head index="03" title={<>Pick an <em>operating point</em>.</>} blurb="No prediction table for this model — the threshold sweep is unavailable." />
          </section>
        )}

        {operating && sweep.data && (
          <section style={{ padding: "76px 0 0" }}>
            <Head
              index="03"
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

        {/* Closing note: a rule and text, deliberately not a card. */}
        <Reveal as="section" delay={80} style={{ padding: "72px 0 0" }}>
          <div className="caps" style={{ marginBottom: 10 }}>
            How to read this
          </div>
          <p style={{ margin: 0, fontSize: 14.5, lineHeight: 1.78, color: "var(--ink-2)", maxWidth: 760 }}>
            The null bounds how much the graph features can be worth on this data, at this label
            density, with this split. The structural signal is still real and still visible — it shows
            up in the{" "}
            <span style={{ color: "var(--ink)", fontWeight: 500 }}>ring ranking</span> above, where
            burst share beats the size-only control by a wide margin. What it does not do is survive
            being folded into a per-transaction classifier that already has the transaction's own
            features.
          </p>
        </Reveal>
      </div>
    </div>
  );
}
