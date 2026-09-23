import { useQuery } from "@tanstack/react-query";
import { api, queryKeys } from "../api/client";
import { CountUp } from "../components/CountUp";
import type { View } from "../views";

interface Props {
  onNavigate: (view: View) => void;
}

function Stat({
  value,
  decimals,
  suffix,
  label,
  note,
  delay,
}: {
  value: number;
  decimals?: number;
  suffix?: string;
  label: string;
  note: string;
  delay: string;
}) {
  return (
    <div className={`rise ${delay}`} style={{ minWidth: 0 }}>
      <div style={{ fontSize: 38, fontWeight: 600, lineHeight: 1.05, letterSpacing: "-0.02em" }}>
        <CountUp value={value} decimals={decimals} suffix={suffix} />
      </div>
      <div className="caps" style={{ marginTop: 6, marginBottom: 2 }}>
        {label}
      </div>
      <div style={{ fontSize: 12, color: "var(--fg-muted)", lineHeight: 1.5 }}>{note}</div>
    </div>
  );
}

function Finding({
  title,
  body,
  verdict,
  tone,
  delay,
}: {
  title: string;
  body: string;
  verdict: string;
  tone: string;
  delay: string;
}) {
  return (
    <div
      className={`rise ${delay}`}
      style={{
        padding: 20,
        borderRadius: 10,
        background: "var(--bg-panel)",
        border: "1px solid var(--border-subtle)",
        transition: "border-color var(--dur-base) var(--ease-out)",
      }}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = "var(--border-strong)")}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = "var(--border-subtle)")}
    >
      <div
        style={{
          display: "inline-block",
          fontSize: 10,
          fontWeight: 600,
          letterSpacing: "0.07em",
          textTransform: "uppercase",
          padding: "3px 8px",
          borderRadius: 999,
          color: tone,
          background: "var(--bg-sunken)",
          border: `1px solid ${tone}`,
          marginBottom: 12,
        }}
      >
        {verdict}
      </div>
      <div style={{ fontSize: 15, fontWeight: 500, marginBottom: 7 }}>{title}</div>
      <div style={{ fontSize: 13, color: "var(--fg-secondary)", lineHeight: 1.65 }}>{body}</div>
    </div>
  );
}

export function Landing({ onNavigate }: Props) {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  const axes = useQuery({ queryKey: queryKeys.axes(), queryFn: api.axes });

  const rings = health.data?.rings ?? 550;
  const clients = health.data?.clients ?? 4762;
  const burst = axes.data?.axes.burst_share.enrichment ?? 1.72;

  return (
    <div>
      {/* Hero. The background is the project's own rendered link graph, not
          stock decoration -- every dot in it is a reconstructed client. */}
      <section
        style={{
          position: "relative",
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "0 clamp(24px, 7vw, 120px)",
          overflow: "hidden",
        }}
      >
        <div
          aria-hidden
          style={{
            position: "absolute",
            inset: "-6%",
            backgroundImage: "url(/graph.png)",
            backgroundSize: "cover",
            backgroundPosition: "center",
            opacity: 0.3,
            animation: "drift 42s var(--ease-out) infinite alternate",
            maskImage: "radial-gradient(ellipse 70% 60% at 62% 45%, black 20%, transparent 78%)",
            WebkitMaskImage:
              "radial-gradient(ellipse 70% 60% at 62% 45%, black 20%, transparent 78%)",
          }}
        />
        <div
          aria-hidden
          style={{
            position: "absolute",
            inset: 0,
            background:
              "linear-gradient(90deg, var(--bg-app) 12%, rgba(15,19,26,0.72) 48%, rgba(15,19,26,0.25) 100%)",
          }}
        />

        <div style={{ position: "relative", maxWidth: 780 }}>
          <div
            className="rise rise-1 caps"
            style={{ marginBottom: 18, color: "var(--accent)" }}
          >
            IEEE-CIS · 590,540 transactions · 182 days
          </div>
          <h1
            className="rise rise-2"
            style={{
              fontSize: "clamp(38px, 5.4vw, 66px)",
              fontWeight: 600,
              lineHeight: 1.04,
              letterSpacing: "-0.03em",
              margin: 0,
            }}
          >
            Relational fraud
            <br />
            intelligence
          </h1>
          <p
            className="rise rise-3"
            style={{
              fontSize: "clamp(15px, 1.5vw, 19px)",
              color: "var(--fg-secondary)",
              lineHeight: 1.65,
              maxWidth: 620,
              marginTop: 22,
            }}
          >
            Organised fraud spreads value across synthetic identities so each transaction looks
            ordinary. This finds the coordination between them — and tests, honestly, whether
            that structure predicts anything a good tabular model misses.
          </p>

          <div className="rise rise-4" style={{ display: "flex", gap: 10, marginTop: 34 }}>
            <button
              onClick={() => onNavigate("investigate")}
              style={{
                fontSize: 14,
                fontWeight: 500,
                padding: "11px 22px",
                borderRadius: 999,
                background: "var(--fg-primary)",
                color: "var(--bg-canvas)",
                transition: "transform var(--dur-base) var(--ease-out)",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.transform = "translateY(-2px)")}
              onMouseLeave={(e) => (e.currentTarget.style.transform = "none")}
            >
              Explore the rings →
            </button>
            <button
              onClick={() => onNavigate("results")}
              style={{
                fontSize: 14,
                fontWeight: 500,
                padding: "11px 22px",
                borderRadius: 999,
                color: "var(--fg-primary)",
                border: "1px solid var(--border-strong)",
                transition: "background var(--dur-base) var(--ease-out)",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.05)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              See the result
            </button>
          </div>
        </div>

        <div
          style={{
            position: "relative",
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
            gap: 30,
            maxWidth: 820,
            marginTop: 72,
            paddingTop: 30,
            borderTop: "1px solid var(--border-subtle)",
          }}
        >
          <Stat
            value={rings}
            label="candidate rings"
            note="detected over the client projection"
            delay="rise-4"
          />
          <Stat
            value={clients}
            label="linked clients"
            note="joined by shared device attributes"
            delay="rise-5"
          />
          <Stat
            value={burst}
            decimals={2}
            suffix="×"
            label="detector enrichment"
            note="fraud found over chance, size-controlled"
            delay="rise-5"
          />
          <Stat
            value={96.6}
            decimals={1}
            suffix="%"
            label="label purity"
            note="the trap this design had to survive"
            delay="rise-6"
          />
        </div>
      </section>

      <section style={{ padding: "0 clamp(24px, 7vw, 120px) 110px", maxWidth: 1240 }}>
        <h2
          style={{
            fontSize: 13,
            fontWeight: 500,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            color: "var(--fg-muted)",
            marginBottom: 20,
          }}
        >
          What it found
        </h2>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(290px, 1fr))",
            gap: 16,
          }}
        >
          <Finding
            verdict="confirmed"
            tone="var(--risk-3)"
            title="The labels are clustered by client"
            body="96.6% of multi-transaction clients are entirely fraudulent or entirely clean, against 85.1% expected by chance. Linking a client's own transactions would have rediscovered the labelling rule, so the thesis was restricted to links between distinct identities before any model was built."
            delay="rise-1"
          />
          <Finding
            verdict="real"
            tone="var(--risk-2)"
            title="Coordination is measurable"
            body="Fraud-bearing groups fire in tighter bursts than clean groups of the same size, and ranking rings by burstiness finds fraud well above chance once ring size is controlled for. The effect reproduces across all three client-reconstruction rules."
            delay="rise-2"
          />
          <Finding
            verdict="null"
            tone="var(--fg-muted)"
            title="But it does not improve prediction"
            body="Graph features add no detectable lift over a tuned tabular baseline — on any stratum, across five seeds, with both models tuned on their own feature sets. Ring detection works; ring structure does not improve per-transaction scoring."
            delay="rise-3"
          />
        </div>
      </section>
    </div>
  );
}
