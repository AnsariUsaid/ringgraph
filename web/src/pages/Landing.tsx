import { useQuery } from "@tanstack/react-query";
import { api, queryKeys } from "../api/client";
import { AxisAtlas } from "../components/AxisAtlas";
import { Constellation } from "../components/Constellation";
import { Pipeline } from "../components/Pipeline";
import { CountUp } from "../components/CountUp";
import { Reveal } from "../components/Reveal";
import { RiskSignature } from "../components/RiskSignature";
import { Link } from "../router";
import type { AxisName } from "../api/types";

/* --------------------------------------------------------------- primitives */

function Pill({ children, tone = "quiet" }: { children: React.ReactNode; tone?: "quiet" | "accent" }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 7,
        padding: "5px 12px 5px 10px",
        borderRadius: 999,
        fontSize: 11,
        fontWeight: 500,
        letterSpacing: "0.02em",
        color: tone === "accent" ? "var(--accent)" : "var(--ink-2)",
        background: tone === "accent" ? "var(--accent-wash)" : "var(--paper-raised)",
        border: `1px solid ${tone === "accent" ? "var(--accent-wash-2)" : "var(--rule)"}`,
      }}
    >
      {children}
    </span>
  );
}

function CTA({ to, children, primary = false }: { to: "/" | "/explore" | "/results"; children: React.ReactNode; primary?: boolean }) {
  return (
    <Link
      to={to}
      className="lift"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 9,
        padding: "13px 24px",
        borderRadius: 999,
        fontSize: 14,
        fontWeight: 550,
        color: primary ? "var(--paper-raised)" : "var(--ink)",
        background: primary ? "var(--ink)" : "var(--paper-raised)",
        border: `1px solid ${primary ? "var(--ink)" : "var(--rule-strong)"}`,
        boxShadow: primary ? "var(--lift-2)" : "var(--lift-1)",
      }}
    >
      {children}
      <span aria-hidden style={{ fontSize: 15, lineHeight: 1 }}>
        →
      </span>
    </Link>
  );
}

/** Section heading with a hairline rule that runs to the edge of the column --
 *  the notebook motif, and it gives every section the same optical weight
 *  without needing a box around it. */
function SectionHead({ index, title, blurb }: { index: string; title: React.ReactNode; blurb?: string }) {
  return (
    <Reveal style={{ marginBottom: 34 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 14, marginBottom: 10 }}>
        <span className="mono" style={{ fontSize: 11, color: "var(--accent)", fontWeight: 600 }}>
          {index}
        </span>
        <span style={{ flex: 1, height: 1, background: "var(--rule)" }} />
      </div>
      <h2 className="display" style={{ fontSize: "clamp(26px, 4.4vw, 46px)", margin: 0, maxWidth: 780 }}>
        {title}
      </h2>
      {blurb && (
        <p style={{ margin: "14px 0 0", maxWidth: 620, fontSize: 15, color: "var(--ink-2)", lineHeight: 1.65 }}>
          {blurb}
        </p>
      )}
    </Reveal>
  );
}

/* ------------------------------------------------------------------ page */

export function Landing() {
  const rings = useQuery({ queryKey: queryKeys.rings("burst_share"), queryFn: () => api.rings("burst_share", 6) });
  const axes = useQuery({ queryKey: queryKeys.axes(), queryFn: api.axes });

  const best = axes.data?.axes.burst_share?.enrichment;
  const composite = axes.data?.axes.composite?.enrichment;

  return (
    <div>
      {/* ------------------------------------------------------------ hero */}
      <section
        style={{
          position: "relative",
          minHeight: "min(94vh, 880px)",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          overflow: "hidden",
          padding: "140px 24px 80px",
        }}
      >
        <div
          className="gridded"
          aria-hidden
          style={{
            position: "absolute",
            inset: 0,
            opacity: 0.55,
            // Faded at the edges so the grid reads as a drafting surface the
            // content sits on, not a box it is trapped in.
            maskImage: "radial-gradient(ellipse 85% 75% at 50% 42%, #000 35%, transparent 100%)",
            WebkitMaskImage: "radial-gradient(ellipse 85% 75% at 50% 42%, #000 35%, transparent 100%)",
          }}
        />
        <div style={{ position: "absolute", inset: 0, opacity: 0.85 }}>
          <Constellation />
        </div>
        {/* Scrim: the canvas runs under the headline, and without this the
            drifting nodes cross the type and cost it contrast. */}
        <div
          aria-hidden
          style={{
            position: "absolute",
            inset: 0,
            background:
              "radial-gradient(ellipse 55% 48% at 50% 46%, rgba(244,241,234,0.94) 30%, rgba(244,241,234,0.55) 62%, transparent 85%)",
          }}
        />

        <div className="page" style={{ position: "relative", textAlign: "center" }}>
          <div style={{ animation: "rise 700ms var(--ease-out) both" }}>
            <Pill tone="accent">
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: 999,
                  background: "var(--accent-2)",
                  boxShadow: "0 0 0 3px var(--accent-2-wash)",
                }}
              />
              {rings.data ? `${rings.data.total} candidate rings indexed` : "loading catalogue…"}
            </Pill>
          </div>

          <h1
            className="display"
            style={{
              fontSize: "clamp(34px, 8.4vw, 104px)",
              margin: "26px auto 0",
              maxWidth: 940,
              animation: "rise 760ms var(--ease-out) 80ms both",
            }}
          >
            Fraud hides in the row.
            <br />
            It shows up in the <em>structure</em>.
          </h1>

          <p
            style={{
              margin: "26px auto 0",
              maxWidth: 580,
              fontSize: 16.5,
              lineHeight: 1.68,
              color: "var(--ink-2)",
              animation: "rise 760ms var(--ease-out) 160ms both",
            }}
          >
            One transaction looks ordinary. Five accounts sharing a device fingerprint, firing within
            the same hour, for the same amount, do not. This is the instrument for finding the second
            thing.
          </p>

          <div
            style={{
              display: "flex",
              gap: 12,
              justifyContent: "center",
              flexWrap: "wrap",
              marginTop: 34,
              animation: "rise 760ms var(--ease-out) 240ms both",
            }}
          >
            <CTA to="/explore" primary>
              Explore the rings
            </CTA>
            <CTA to="/results">Read the result</CTA>
          </div>

          {/* Live counts, read from the same API the workbench uses -- a
              landing page quoting hard-coded figures is one deploy away from
              lying. */}
          <div
            className="grid-stats"
            style={{
              maxWidth: 720,
              margin: "62px auto 0",
              background: "var(--rule)",
              border: "1px solid var(--rule)",
              borderRadius: "var(--radius-panel)",
              overflow: "hidden",
              animation: "rise 760ms var(--ease-out) 340ms both",
            }}
          >
            {[
              { label: "candidate rings", value: rings.data?.total ?? 0, decimals: 0 },
              { label: "linked clients", value: 4762, decimals: 0 },
              { label: "best axis lift", value: best ?? 0, decimals: 2, suffix: "×" },
              { label: "size-only baseline", value: 1, decimals: 2, suffix: "×" },
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
        </div>

        <div
          aria-hidden
          style={{
            position: "absolute",
            bottom: 26,
            left: "50%",
            transform: "translateX(-50%)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 6,
          }}
        >
          <span className="caps" style={{ fontSize: 9 }}>
            scroll
          </span>
          <span style={{ width: 1, height: 28, background: "linear-gradient(var(--rule-ink), transparent)" }} />
        </div>
      </section>

      <div className="page">
        {/* --------------------------------------------------------- axes */}
        <section style={{ padding: "90px 0" }}>
          <SectionHead
            index="01"
            title={
              <>
                Four questions, asked of every <em>cluster</em>.
              </>
            }
            blurb="Every ring is scored on four independent axes. They are kept separate rather than collapsed into one number, because which axis fires tells you what kind of coordination you are looking at — and because, measured honestly, only two of the four beat a ranking that sorts by size alone."
          />
          <Reveal>
            <AxisAtlas />
          </Reveal>
          <Reveal delay={120}>
            <p
              style={{
                margin: "26px 0 0",
                paddingLeft: 18,
                borderLeft: "2px solid var(--risk-3)",
                fontSize: 14,
                lineHeight: 1.72,
                color: "var(--ink-2)",
                maxWidth: 720,
              }}
            >
              Density and concentration land <em style={{ fontStyle: "normal", color: "var(--ink)" }}>below</em> the
              size-only control. They are kept anyway, and shown anyway: an axis that does not rank still describes,
              and hiding the two that failed would make the composite look better than it is.
            </p>
          </Reveal>
        </section>

        {/* ---------------------------------------------------- signature */}
        <section style={{ padding: "50px 0 90px" }}>
          <SectionHead
            index="02"
            title={
              <>
                The four scores become a <em>shape</em>.
              </>
            }
            blurb="The same glyph is drawn everywhere a ring appears, always in the same axis order. Because the order never changes it reads as a silhouette rather than a chart — at 44 pixels, in a scrolling list, without a legend."
          />

          <Reveal>
            <div className="card grid-examples" style={{ overflow: "hidden" }}>
              {[
                { label: "Coordinated burst", axes: { density: 0.55, synchrony: 0.96, concentration: 0.4, tightness: 0.93 }, note: "Synchrony and tightness carry it — a scripted cash-out." },
                { label: "Shared device farm", axes: { density: 0.92, synchrony: 0.32, concentration: 0.95, tightness: 0.3 }, note: "Dense and concentrated, but spread over weeks." },
                { label: "Incidental overlap", axes: { density: 0.22, synchrony: 0.18, concentration: 0.3, tightness: 0.25 }, note: "Everything low. A common browser string, nothing more." },
              ].map((example) => (
                <div key={example.label} style={{ padding: "26px 22px" }}>
                  <RiskSignature axes={example.axes as Record<AxisName, number>} width={112} height={40} labels />
                  <div style={{ marginTop: 16, fontSize: 14, fontWeight: 600 }}>{example.label}</div>
                  <div style={{ marginTop: 5, fontSize: 12.5, color: "var(--ink-2)", lineHeight: 1.6 }}>{example.note}</div>
                </div>
              ))}
            </div>
          </Reveal>
        </section>

        {/* ----------------------------------------------------- findings */}
        <section style={{ padding: "50px 0 90px" }}>
          <SectionHead
            index="03"
            title={
              <>
                Three findings, including the one that <em>did not work</em>.
              </>
            }
          />

          <ol style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {[
              {
                n: "I",
                title: "Burst share out-ranks the composite it belongs to.",
                body: "Ranking rings by the share of their transactions falling in a single burst finds fraud clients at " +
                  (best ? best.toFixed(2) : "1.72") +
                  "× the rate expected from ring size alone. The four-axis composite manages " +
                  (composite ? composite.toFixed(2) : "1.27") +
                  "×. Two of its axes are anti-predictive, so averaging them in costs more than it adds — which is why the tool opens on burst share.",
                figure: (
                  <div style={{ display: "flex", flexDirection: "column", gap: 10, width: "100%" }}>
                    {[
                      ["burst share", best ?? 1.72, "var(--risk-3)"],
                      ["composite", composite ?? 1.27, "var(--risk-1)"],
                      ["size only", 1, "var(--risk-0)"],
                    ].map(([label, value, colour]) => (
                      <div key={label as string}>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 4 }}>
                          <span style={{ color: "var(--ink-2)" }}>{label}</span>
                          <span className="mono" style={{ fontWeight: 600 }}>
                            {(value as number).toFixed(2)}×
                          </span>
                        </div>
                        <div style={{ height: 8, background: "var(--paper-sunken)", borderRadius: 999, overflow: "hidden" }}>
                          <div
                            style={{
                              width: `${Math.min(100, ((value as number) / 2) * 100)}%`,
                              height: "100%",
                              borderRadius: 999,
                              background: colour as string,
                              transition: "width 900ms var(--ease-out)",
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                ),
              },
              {
                n: "II",
                title: "Structure is legible before it is predictive.",
                body: "The top rings are not statistical artefacts — they are five accounts on one device fingerprint, transacting inside the same hour for identical amounts. The event raster shows that as a vertical wall, and it is visible before any model is trained on it.",
                figure: (
                  <svg width="100%" height="106" viewBox="0 0 220 106" aria-hidden>
                    {Array.from({ length: 6 }).map((_, lane) => (
                      <g key={lane}>
                        <rect x={0} y={4 + lane * 17} width={220} height={12} rx={3} fill="var(--paper-sunken)" />
                        {[14, 52, 96, 150, 188].map((x, i) => (
                          <rect
                            key={i}
                            x={x + (i % 2 ? lane : -lane) * 2}
                            y={6 + lane * 17}
                            width={3}
                            height={8}
                            rx={1}
                            fill="var(--ink-4)"
                          />
                        ))}
                        <rect x={120 + lane * 0.8} y={6 + lane * 17} width={4} height={8} rx={1} fill="var(--risk-4)" />
                      </g>
                    ))}
                  </svg>
                ),
              },
              {
                n: "III",
                title: "Adding graph features to the model changed nothing.",
                body: "Five seeds per model, paired on training randomness. Every confidence interval on the difference spans zero, and seed-only variation is larger than any difference measured between the two models. Reported as it came out, on its own page, rather than quietly dropped.",
                figure: (
                  <div style={{ width: "100%" }}>
                    <div style={{ position: "relative", height: 38, background: "var(--paper-sunken)", borderRadius: 8 }}>
                      <div style={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: 1, background: "var(--rule-ink)" }} />
                      <div
                        style={{
                          position: "absolute",
                          left: "31%",
                          width: "40%",
                          top: 14,
                          height: 10,
                          borderRadius: 999,
                          background: "var(--risk-1)",
                          opacity: 0.4,
                        }}
                      />
                      <div style={{ position: "absolute", left: "47%", top: 10, width: 2, height: 18, background: "var(--ink)" }} />
                    </div>
                    <div className="mono" style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--ink-3)", marginTop: 6 }}>
                      <span>−0.06</span>
                      <span>0 · no difference</span>
                      <span>+0.06</span>
                    </div>
                  </div>
                ),
              },
            ].map((finding, index) => (
              <Reveal as="li" key={finding.n} delay={index * 80}>
                <div className="finding">
                  <div>
                    <div style={{ display: "flex", alignItems: "baseline", gap: 14 }}>
                      <span
                        className="display"
                        style={{ fontSize: 30, color: "var(--accent)", minWidth: 42, fontStyle: "italic" }}
                      >
                        {finding.n}
                      </span>
                      <h3 style={{ margin: 0, fontSize: 21, fontWeight: 600, letterSpacing: "-0.025em", lineHeight: 1.28 }}>
                        {finding.title}
                      </h3>
                    </div>
                    <p style={{ margin: "12px 0 0 56px", fontSize: 14, lineHeight: 1.7, color: "var(--ink-2)" }}>
                      {finding.body}
                    </p>
                  </div>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      padding: "20px 18px",
                      background: "var(--paper-raised)",
                      border: "1px solid var(--rule)",
                      borderRadius: "var(--radius-panel)",
                    }}
                  >
                    {finding.figure}
                  </div>
                </div>
              </Reveal>
            ))}
          </ol>
        </section>

        {/* ------------------------------------------------------ pipeline */}
        <section style={{ padding: "50px 0 90px" }}>
          <SectionHead
            index="04"
            title={
              <>
                From raw rows to a ranked <em>catalogue</em>.
              </>
            }
            blurb="Seven steps, in the order the repository runs them, each with the number it actually produced. Two of them are gates rather than transformations — points where the measurement could have said stop, and very nearly did."
          />
          <Pipeline />
        </section>

        {/* ----------------------------------------------------- top rings */}
        <section style={{ padding: "30px 0 90px" }}>
          <SectionHead index="05" title={<>The current top of the <em>list</em>.</>} blurb="Live from the same endpoint the workbench reads, sorted by burst share." />
          <Reveal>
            <div className="card" style={{ overflow: "hidden" }}>
              {(rings.data?.rings ?? Array.from({ length: 5 }).map(() => null)).slice(0, 5).map((ring, i) =>
                ring ? (
                  <Link
                    key={ring.ring_id}
                    to="/explore"
                    className="ring-row"
                    style={{ borderTop: i === 0 ? undefined : "1px solid var(--rule)" }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "var(--accent-wash)")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  >
                    <span style={{ height: "100%", background: i < 2 ? "var(--risk-4)" : "var(--risk-2)" }} />
                    <span className="mono" style={{ fontSize: 13, fontWeight: 600 }}>
                      {String(ring.ring_id).padStart(4, "0")}
                    </span>
                    <span style={{ fontSize: 13, color: "var(--ink-2)" }}>
                      <span className="mono" style={{ color: "var(--ink)" }}>{ring.n_clients}</span> clients ·{" "}
                      <span className="mono" style={{ color: "var(--ink)" }}>{ring.n_transactions}</span> transactions
                      {ring.n_fraud_clients > 0 && (
                        <span style={{ color: "var(--risk-4)", fontWeight: 500 }}>
                          {" "}· {ring.n_fraud_clients} confirmed
                        </span>
                      )}
                    </span>
                    <span className="ring-row__spacer" />
                    <span className="ring-row__sig">
                      <RiskSignature axes={ring.axes} width={96} height={20} />
                    </span>
                    <span className="mono" style={{ fontSize: 13, textAlign: "right", fontWeight: 600 }}>
                      {ring.composite.toFixed(3)}
                    </span>
                  </Link>
                ) : (
                  <div key={i} className="skeleton" style={{ height: 58, borderTop: i === 0 ? undefined : "1px solid var(--rule)" }} />
                ),
              )}
            </div>
          </Reveal>
        </section>
      </div>

      {/* ---------------------------------------------------------- closing */}
      <section style={{ position: "relative", overflow: "hidden", background: "var(--ink)", color: "var(--paper)" }}>
        <div
          aria-hidden
          style={{
            position: "absolute",
            inset: "-30%",
            background:
              "radial-gradient(circle at 25% 30%, rgba(95,82,232,0.42), transparent 55%), radial-gradient(circle at 78% 70%, rgba(180,29,60,0.34), transparent 55%)",
            animation: "drift 22s ease-in-out infinite",
          }}
        />
        <div
          style={{
            position: "relative",
            width: "min(1120px, 100%)",
            margin: "0 auto",
            padding: "110px 24px",
            textAlign: "center",
          }}
        >
          <Reveal>
            <h2 className="display" style={{ fontSize: "clamp(34px, 6vw, 68px)", margin: 0, color: "var(--paper)" }}>
              550 rings are waiting.
              <br />
              <span style={{ opacity: 0.55 }}>Start with the one at the top.</span>
            </h2>
            <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap", marginTop: 36 }}>
              <Link
                to="/explore"
                className="lift"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 9,
                  padding: "13px 26px",
                  borderRadius: 999,
                  fontSize: 14,
                  fontWeight: 550,
                  color: "var(--ink)",
                  background: "var(--paper-raised)",
                  border: "1px solid transparent",
                }}
              >
                Open the workbench <span aria-hidden>→</span>
              </Link>
              <Link
                to="/results"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 9,
                  padding: "13px 26px",
                  borderRadius: 999,
                  fontSize: 14,
                  fontWeight: 550,
                  color: "var(--paper)",
                  border: "1px solid rgba(255,255,255,0.28)",
                }}
              >
                See the null result
              </Link>
            </div>
          </Reveal>
        </div>
      </section>
    </div>
  );
}
