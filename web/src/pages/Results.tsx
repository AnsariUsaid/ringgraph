import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Area, AreaChart, CartesianGrid, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
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

function PageHead() {
  return (
    <header style={{ padding: "calc(var(--nav-height) + 64px) 0 10px" }}>
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
        paired on training randomness, scored as true-positive rate at a 1% false-positive rate. What
        follows is the answer that came out, not the one the project was hoping for.
      </p>
    </header>
  );
}

function Card({
  title,
  note,
  children,
  delay = 0,
}: {
  title: string;
  note?: string;
  children: React.ReactNode;
  delay?: number;
}) {
  return (
    <Reveal delay={delay} as="section" className="card" style={{ padding: "24px 24px 26px" }}>
      <div className="caps">{title}</div>
      {note && (
        <p style={{ margin: "8px 0 20px", fontSize: 13, color: "var(--ink-2)", lineHeight: 1.6, maxWidth: 640 }}>
          {note}
        </p>
      )}
      {!note && <div style={{ height: 18 }} />}
      {children}
    </Reveal>
  );
}

export function Results() {
  const [threshold, setThreshold] = useState(0.99);
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

  /** Half-width of the difference axis, in TPR points.
   *
   * Derived from the data rather than fixed: these strata differ in spread by
   * an order of magnitude, and a hard-coded scale clipped the widest band
   * against both ends of its track -- which reads as a bar that ran out of
   * room, exactly the opposite of "this estimate is uncertain". */
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

  return (
    <div className="page page--narrow" style={{ paddingBottom: 110 }}>
      <PageHead />

      {models.isError && (
        <div className="card" style={{ marginTop: 40, height: 240 }}>
          <StatePanel title="Could not load model metrics" tone="error" />
        </div>
      )}

      {models.data && verdict && (
        <Reveal style={{ margin: "48px 0 20px" }}>
          <div className="card verdict" style={{ overflow: "hidden" }}>
            <div style={{ padding: "34px 30px", background: "var(--paper-sunken)" }}>
              <div className="caps">Verdict</div>
              <div
                className="display"
                style={{ fontSize: 42, margin: "12px 0 0", lineHeight: 1.06 }}
              >
                {verdict.spanning === verdict.total ? (
                  <>
                    No measurable
                    <br />
                    <em>difference</em>.
                  </>
                ) : (
                  <>
                    {verdict.spanning} of {verdict.total} intervals span <em>zero</em>.
                  </>
                )}
              </div>
              <p style={{ margin: "16px 0 0", fontSize: 13, lineHeight: 1.65, color: "var(--ink-2)" }}>
                {models.data.seed_note}
              </p>
              <div style={{ display: "flex", gap: 26, marginTop: 24 }}>
                {[
                  ["seeds per model", 5],
                  ["strata", verdict.total],
                  ["intervals spanning 0", verdict.spanning],
                ].map(([label, value]) => (
                  <div key={label as string}>
                    <div style={{ fontSize: 24, fontWeight: 600, letterSpacing: "-0.03em" }}>
                      <CountUp to={value as number} />
                    </div>
                    <div className="caps" style={{ marginTop: 2 }}>
                      {label}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ padding: "34px 30px" }}>
              <div className="caps" style={{ marginBottom: 4 }}>
                Paired difference · M2 minus M1
              </div>
              <p style={{ margin: "0 0 22px", fontSize: 12.5, color: "var(--ink-2)", lineHeight: 1.6 }}>
                Tick is the mean, band is ±1 sd of the paired difference. The centre line is “the two
                models are the same”.
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                {Object.entries(models.data.structural).map(([stratum, result]) => {
                  const toPct = (value: number) => 50 + (value / half) * 50;
                  return (
                    <div key={stratum}>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 6 }}>
                        <span style={{ color: "var(--ink-2)" }}>{STRATUM_LABELS[stratum] ?? stratum}</span>
                        <span className="mono" style={{ color: "var(--ink)", fontWeight: 500 }}>
                          {result.mean_diff >= 0 ? "+" : ""}
                          {result.mean_diff.toFixed(4)}
                          <span style={{ color: "var(--ink-3)" }}> · {result.wins}/{result.n_seeds} seeds</span>
                        </span>
                      </div>
                      <div style={{ position: "relative", height: 26, background: "var(--paper-sunken)", borderRadius: 7 }}>
                        <div style={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: 1, background: "var(--rule-ink)" }} />
                        <div
                          style={{
                            position: "absolute",
                            left: `${toPct(result.mean_diff - result.sd_diff)}%`,
                            width: `${(2 * result.sd_diff / half) * 50}%`,
                            top: 8,
                            height: 10,
                            borderRadius: 999,
                            background: "var(--risk-1)",
                            opacity: 0.45,
                          }}
                        />
                        <div
                          style={{
                            position: "absolute",
                            left: `${toPct(result.mean_diff)}%`,
                            top: 4,
                            width: 2,
                            height: 18,
                            background: "var(--ink)",
                          }}
                        />
                        {/* Per-seed marks: five points is few enough to show
                            individually, and seeing them scattered on both
                            sides of zero is more convincing than any interval. */}
                        {result.per_seed_diffs.map((diff, i) => (
                          <div
                            key={i}
                            title={`seed ${i + 1}: ${diff >= 0 ? "+" : ""}${diff.toFixed(4)}`}
                            style={{
                              position: "absolute",
                              left: `${toPct(diff)}%`,
                              top: 17,
                              width: 5,
                              height: 5,
                              marginLeft: -2.5,
                              borderRadius: 999,
                              background: "var(--ink-3)",
                            }}
                          />
                        ))}
                      </div>
                    </div>
                  );
                })}

                {/* One shared axis under the three tracks, because they are
                    drawn to the same scale and three separate rulers would
                    invite reading them as three different ones. */}
                <div
                  className="mono"
                  style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--ink-3)" }}
                >
                  <span>−{half.toFixed(2)}</span>
                  <span>0 · no difference</span>
                  <span>+{half.toFixed(2)}</span>
                </div>
              </div>
            </div>
          </div>
        </Reveal>
      )}

      <div style={{ display: "grid", gap: 20, marginTop: 20 }}>
        {axes.data && (
          <Card
            key="axes"
            title="Ring-ranking power by axis"
            note={`Fraud clients found in the top ${axes.data.k} rings, over the number expected from ring size alone. A ranking that only sorts by size scores 1.00× — anything at or below that line is not finding structure, it is finding big clusters.`}
            delay={60}
          >
            <div style={{ display: "flex", flexDirection: "column", gap: 11 }}>
              {Object.entries(axes.data.axes)
                .sort((a, b) => b[1].enrichment - a[1].enrichment)
                .map(([axis, value]) => {
                  const beats = value.enrichment >= 1;
                  const best = axis === "burst_share";
                  return (
                    <div
                      key={axis}
                      style={{
                        display: "grid",
                        gridTemplateColumns: "140px minmax(0, 1fr) 62px",
                        gap: 14,
                        alignItems: "center",
                      }}
                    >
                      <div>
                        <div style={{ fontSize: 13, fontWeight: best ? 600 : 500, color: beats ? "var(--ink)" : "var(--ink-3)" }}>
                          {axis.replace("_", " ")}
                        </div>
                        <div style={{ fontSize: 10.5, color: "var(--ink-3)", lineHeight: 1.35 }}>{AXIS_BLURB[axis]}</div>
                      </div>
                      <div style={{ position: "relative", height: 16, background: "var(--paper-sunken)", borderRadius: 6 }}>
                        {/* The 1.00x control line. Without it every bar looks
                            like a win. */}
                        <div style={{ position: "absolute", left: "50%", top: -3, bottom: -3, width: 1, background: "var(--rule-ink)", zIndex: 1 }} />
                        <div
                          style={{
                            width: `${Math.min(100, (value.enrichment / 2) * 100)}%`,
                            height: "100%",
                            borderRadius: 6,
                            background: best ? "var(--risk-3)" : beats ? "var(--risk-1)" : "var(--risk-0)",
                            transition: "width 700ms var(--ease-out)",
                          }}
                        />
                      </div>
                      <span
                        className="mono"
                        style={{ textAlign: "right", fontSize: 13, fontWeight: best ? 600 : 500, color: beats ? "var(--ink)" : "var(--ink-3)" }}
                      >
                        {value.enrichment.toFixed(2)}×
                      </span>
                    </div>
                  );
                })}
            </div>
          </Card>
        )}

        {sweep.isError && (
          <Card key="sweep-error" title="Operating point" note="No prediction table for this model — the threshold sweep is unavailable." delay={60}>
            <div style={{ height: 40 }} />
          </Card>
        )}

        {operating && sweep.data && (
          <Card
            key="operating"
            title="Operating point · M1 tuned"
            note="The full sweep is fetched once, so dragging the threshold is a lookup rather than a request per frame. The dot tracks your position on the ROC curve."
            delay={80}
          >
            <div className="operating">
              <div style={{ height: 250, margin: "0 -8px" }}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={curve} margin={{ top: 6, right: 8, bottom: 2, left: -18 }}>
                    <defs>
                      <linearGradient id="roc" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.22} />
                        <stop offset="100%" stopColor="var(--accent)" stopOpacity={0.02} />
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
                    <Area type="monotone" dataKey="tpr" stroke="var(--accent)" strokeWidth={2} fill="url(#roc)" isAnimationActive={false} />
                    <ReferenceDot x={operating.fpr} y={operating.tpr} r={5} fill="var(--risk-4)" stroke="var(--paper-raised)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
                <div className="caps" style={{ textAlign: "center", marginTop: -4 }}>
                  false-positive rate → true-positive rate
                </div>
              </div>

              <div>
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
                <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 4 }}>
                  threshold {operating.threshold.toFixed(3)}
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1, marginTop: 18, background: "var(--rule)", border: "1px solid var(--rule)", borderRadius: 12, overflow: "hidden" }}>
                  {[
                    ["caught", operating.tp.toLocaleString(), "var(--accent-2)"],
                    ["missed", operating.fn.toLocaleString(), "var(--ink-3)"],
                    ["false alarms", operating.fp.toLocaleString(), "var(--risk-3)"],
                    ["FPR", `${(operating.fpr * 100).toFixed(2)}%`, "var(--ink)"],
                  ].map(([label, value, colour]) => (
                    <div key={label} style={{ background: "var(--paper-raised)", padding: "12px 14px" }}>
                      <div className="caps" style={{ marginBottom: 2 }}>
                        {label}
                      </div>
                      <div className="mono" style={{ fontSize: 18, fontWeight: 600, color: colour }}>
                        {value}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </Card>
        )}

        <Reveal key="how-to-read" delay={100} as="section" className="card" style={{ padding: "22px 24px" }}>
          <div className="caps" style={{ marginBottom: 8 }}>
            How to read this
          </div>
          <p style={{ margin: 0, fontSize: 13, lineHeight: 1.72, color: "var(--ink-2)", maxWidth: 760 }}>
            A null is not a failed experiment — it is a measured bound on how much the graph features
            can be worth on this data, at this label density, with this split. The structural signal
            is still real and still visible: it shows up in the{" "}
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
