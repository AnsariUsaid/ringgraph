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
      <div
        className="text-gradient"
        style={{ fontSize: 42, fontWeight: 600, lineHeight: 1.02, letterSpacing: "-0.025em" }}
      >
        <CountUp value={value} decimals={decimals} suffix={suffix} />
      </div>
      <div className="caps" style={{ marginTop: 9, marginBottom: 3, color: "var(--fg-secondary)" }}>
        {label}
      </div>
      <div style={{ fontSize: 12.5, color: "var(--fg-muted)", lineHeight: 1.55 }}>{note}</div>
    </div>
  );
}

/** A finding, set as an editorial entry rather than a card.
 *
 * Three bordered boxes in a row is the default shape every dashboard reaches
 * for, and it makes unequal findings look equal. These are numbered, unequal in
 * weight, and each carries the one figure that supports it — which is closer to
 * how the finding is actually argued.
 */
function Finding({
  index,
  verdict,
  title,
  body,
  figure,
  figureNote,
  delay,
}: {
  index: string;
  verdict: string;
  title: string;
  body: string;
  figure: string;
  figureNote: string;
  delay: string;
}) {
  return (
    <div
      className={`rise ${delay}`}
      style={{
        display: "grid",
        gridTemplateColumns: "minmax(0, 76px) minmax(0, 1fr) minmax(0, 250px)",
        gap: "clamp(20px, 4vw, 56px)",
        alignItems: "start",
        padding: "38px 0",
        borderTop: "1px solid var(--border-subtle)",
      }}
    >
      <div
        className="mono"
        style={{ fontSize: 34, fontWeight: 600, color: "var(--border-strong)", lineHeight: 1 }}
      >
        {index}
      </div>

      <div>
        <div
          className="caps"
          style={{ color: "var(--signature-a)", marginBottom: 10, letterSpacing: "0.1em" }}
        >
          {verdict}
        </div>
        <h3
          style={{
            fontSize: "clamp(21px, 2.3vw, 28px)",
            fontWeight: 600,
            letterSpacing: "-0.02em",
            lineHeight: 1.22,
            margin: "0 0 12px",
          }}
        >
          {title}
        </h3>
        <p
          style={{
            fontSize: 14.5,
            color: "var(--fg-secondary)",
            lineHeight: 1.72,
            margin: 0,
            maxWidth: 600,
          }}
        >
          {body}
        </p>
      </div>

      <div
        style={{
          padding: "18px 20px",
          borderRadius: 10,
          background: "rgba(255,255,255,0.025)",
          border: "1px solid var(--border-subtle)",
          transition: "box-shadow var(--dur-base) var(--ease-out), transform var(--dur-base) var(--ease-out)",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.boxShadow = "var(--glow-signature)";
          e.currentTarget.style.transform = "translateY(-2px)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.boxShadow = "none";
          e.currentTarget.style.transform = "none";
        }}
      >
        <div className="mono" style={{ fontSize: 27, fontWeight: 600, letterSpacing: "-0.02em" }}>
          {figure}
        </div>
        <div style={{ fontSize: 12, color: "var(--fg-muted)", marginTop: 7, lineHeight: 1.55 }}>
          {figureNote}
        </div>
      </div>
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
    <div style={{ position: "relative", overflow: "hidden" }}>
      <section
        style={{
          position: "relative",
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "120px clamp(24px, 7vw, 120px) 70px",
        }}
      >
        <div className="aurora" aria-hidden />
        {/* The project's own link graph, not stock texture: every dot is a
            reconstructed client. Masked so it reads as depth behind the type. */}
        <div
          aria-hidden
          style={{
            position: "absolute",
            inset: "-6%",
            backgroundImage: "url(/graph.png)",
            backgroundSize: "cover",
            backgroundPosition: "center",
            opacity: 0.34,
            animation: "drift 46s var(--ease-out) infinite alternate",
            maskImage: "radial-gradient(ellipse 66% 58% at 66% 44%, black 16%, transparent 76%)",
            WebkitMaskImage:
              "radial-gradient(ellipse 66% 58% at 66% 44%, black 16%, transparent 76%)",
          }}
        />
        <div
          aria-hidden
          style={{
            position: "absolute",
            inset: 0,
            background:
              "linear-gradient(94deg, var(--bg-app) 8%, rgba(15,19,26,0.78) 46%, rgba(15,19,26,0.2) 100%)",
          }}
        />

        <div style={{ position: "relative", maxWidth: 800 }}>
          <div
            className="rise rise-1"
            style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 22 }}
          >
            <span
              style={{
                width: 22,
                height: 2,
                borderRadius: 2,
                background: "var(--grad-signature)",
              }}
            />
            <span className="caps" style={{ color: "var(--fg-secondary)", letterSpacing: "0.12em" }}>
              IEEE-CIS · 590,540 transactions · 182 days
            </span>
          </div>

          <h1
            className="rise rise-2"
            style={{
              fontSize: "clamp(40px, 5.8vw, 72px)",
              fontWeight: 600,
              lineHeight: 1.02,
              letterSpacing: "-0.035em",
              margin: 0,
            }}
          >
            Finding the <span className="text-gradient">coordination</span>
            <br />
            behind ordinary fraud
          </h1>

          <p
            className="rise rise-3"
            style={{
              fontSize: "clamp(15px, 1.5vw, 19px)",
              color: "var(--fg-secondary)",
              lineHeight: 1.68,
              maxWidth: 630,
              marginTop: 24,
            }}
          >
            Organised rings spread value across synthetic identities so every transaction looks
            unremarkable on its own. This reconstructs who is really who, links them by the devices
            they share, and measures whether the structure between them holds a signal.
          </p>

          <div className="rise rise-4" style={{ display: "flex", gap: 12, marginTop: 38 }}>
            <button
              onClick={() => onNavigate("investigate")}
              style={{
                fontSize: 14.5,
                fontWeight: 600,
                padding: "13px 26px",
                borderRadius: 999,
                background: "var(--grad-signature)",
                color: "#04140f",
                transition:
                  "transform var(--dur-base) var(--ease-spring), box-shadow var(--dur-base) var(--ease-out)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = "translateY(-3px)";
                e.currentTarget.style.boxShadow = "0 16px 44px -12px rgba(110,231,165,0.55)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = "none";
                e.currentTarget.style.boxShadow = "none";
              }}
            >
              Explore the rings
            </button>
            <button
              onClick={() => onNavigate("results")}
              className="edge-lit"
              style={{
                fontSize: 14.5,
                fontWeight: 500,
                padding: "13px 26px",
                borderRadius: 999,
                color: "var(--fg-primary)",
                background: "rgba(255,255,255,0.04)",
                border: "1px solid var(--border-default)",
                transition: "background var(--dur-base) var(--ease-out), transform var(--dur-base) var(--ease-spring)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "rgba(255,255,255,0.09)";
                e.currentTarget.style.transform = "translateY(-3px)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "rgba(255,255,255,0.04)";
                e.currentTarget.style.transform = "none";
              }}
            >
              Read the result
            </button>
          </div>
        </div>

        <div
          style={{
            position: "relative",
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
            gap: 34,
            maxWidth: 880,
            marginTop: 80,
            paddingTop: 34,
            borderTop: "1px solid var(--border-subtle)",
          }}
        >
          <Stat value={rings} label="candidate rings" note="over the client projection" delay="rise-4" />
          <Stat value={clients} label="linked clients" note="joined by shared devices" delay="rise-5" />
          <Stat
            value={burst}
            decimals={2}
            suffix="×"
            label="detector enrichment"
            note="fraud over chance, size-controlled"
            delay="rise-5"
          />
          <Stat value={96.6} decimals={1} suffix="%" label="label purity" note="the trap this had to survive" delay="rise-6" />
        </div>
      </section>

      <section
        style={{
          position: "relative",
          padding: "0 clamp(24px, 7vw, 120px) 120px",
          maxWidth: 1280,
        }}
      >
        <h2
          className="caps"
          style={{ color: "var(--fg-muted)", marginBottom: 6, letterSpacing: "0.12em" }}
        >
          What it found
        </h2>
        <Finding
          index="01"
          verdict="confirmed before any model was built"
          title="The labels are clustered by client, not by transaction"
          body="Almost every customer in this dataset is entirely fraudulent or entirely clean. Build a graph linking a customer's own transactions and you would 'discover' that fraud forms dense clusters — having rediscovered the labelling rule, not detected anything. Measuring it first forced the thesis to rest only on links between distinct identities."
          figure="+11.5 pts"
          figureNote="label purity above what chance and client sizes alone produce"
          delay="rise-1"
        />
        <Finding
          index="02"
          verdict="measured, and it reproduces"
          title="Coordinated groups fire in bursts that ordinary customers do not"
          body="Clients sharing a device fingerprint transact in tight windows far more often than clean groups of the same size. Ranking rings by that burstiness finds fraud well above chance once ring size is controlled for — and the effect holds under all three client-reconstruction rules, so it is not an artefact of how identity was inferred."
          figure="2.72×"
          figureNote="fraud enrichment among small rings, against a size-matched null"
          delay="rise-2"
        />
      </section>
    </div>
  );
}
