import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, queryKeys } from "../api/client";
import { AXIS_ORDER, type AxisName } from "../api/types";

interface AxisSpec {
  key: AxisName;
  title: string;
  question: string;
  definition: string;
  /** Written as an expression rather than prose: four axes described only in
   *  words read as four synonyms for "suspicious". */
  formula: string;
  fires: string;
  blind: string;
}

const SPECS: Record<AxisName, AxisSpec> = {
  density: {
    key: "density",
    title: "Density",
    question: "How tightly are they wired together?",
    definition:
      "The share of possible client-to-client links inside the ring that actually exist. A ring bought as a package is close to complete; an accidental grouping is a chain.",
    formula: "edges / (n × (n − 1) / 2)",
    fires: "Every member shares an attribute with every other member.",
    blind: "A chain. A–B–C–D is genuinely connected and correctly scores low.",
  },
  synchrony: {
    key: "synchrony",
    title: "Synchrony",
    question: "Did they move at the same moment?",
    definition:
      "How concentrated the ring's transactions are in time, measured against what a ring of that size would produce by chance.",
    formula: "max transactions in a 1h window / total",
    fires: "Scripted cash-out. It draws a vertical wall in the event raster.",
    blind: "A patient farm that spreads the same behaviour over weeks.",
  },
  concentration: {
    key: "concentration",
    title: "Concentration",
    question: "How few attributes carry the whole group?",
    definition:
      "How much of the ring's linkage rests on its single most-shared attribute. One fingerprint holding twelve accounts is a different object from twelve accounts with a browser in common.",
    formula: "max attribute degree / n clients",
    fires: "A single device fingerprint doing all the connecting.",
    blind: "Popular attributes. A common browser string scores high and means nothing.",
  },
  tightness: {
    key: "tightness",
    title: "Tightness",
    question: "Do the amounts repeat?",
    definition:
      "The spread of transaction values inside the ring, inverted, so that a ring which reuses one number scores high.",
    formula: "1 − (sd of amount / mean amount)",
    fires: "A script that picks a figure and reuses it. The top ring is five clients, five transactions, $25 each.",
    blind: "An operator who varies amounts on purpose.",
  },
};

/* ------------------------------------------------------------------ figures */

/** One figure per axis, at a size where it can carry the explanation rather
 *  than decorate it. Each replays its entrance when selected -- the panel is
 *  keyed on the axis, so these remount and the CSS animations restart. */
function Figure({ axis }: { axis: AxisName }) {
  const W = 300;
  const H = 190;

  if (axis === "density") {
    const points = [
      [80, 42],
      [206, 58],
      [232, 132],
      [128, 158],
      [52, 108],
    ];
    const edges: [number[], number[], number][] = [];
    points.forEach((a, i) => points.slice(i + 1).forEach((b, j) => edges.push([a, b, i * 5 + j])));
    return (
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} aria-hidden>
        {edges.map(([a, b], i) => (
          <line
            key={i}
            x1={a[0]}
            y1={a[1]}
            x2={b[0]}
            y2={b[1]}
            stroke="var(--accent)"
            strokeWidth={1.4}
            opacity={0.5}
            className="fig-draw"
            style={{ ["--dash" as string]: "260", animationDelay: `${i * 55}ms` }}
          />
        ))}
        {points.map(([x, y], i) => (
          <circle
            key={i}
            cx={x}
            cy={y}
            r={9}
            fill="var(--accent)"
            className="fig-pop"
            style={{ animationDelay: `${500 + i * 70}ms` }}
          />
        ))}
      </svg>
    );
  }

  if (axis === "synchrony") {
    return (
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} aria-hidden>
        {Array.from({ length: 6 }).map((_, lane) => {
          const y = 18 + lane * 27;
          return (
            <g key={lane} className="fig-slide" style={{ animationDelay: `${lane * 80}ms` }}>
              <rect x={0} y={y} width={W} height={18} rx={5} fill="var(--paper-sunken)" />
              {[24, 62, 98, 214, 266].map((x, i) => (
                <rect key={i} x={x + ((i + lane) % 3) * 6} y={y + 3} width={4} height={12} rx={2} fill="var(--ink-4)" />
              ))}
              {/* The wall: every lane fires inside the same window. */}
              <rect
                x={152 + lane}
                y={y + 2}
                width={6}
                height={14}
                rx={2}
                fill="var(--risk-4)"
                className="fig-pop"
                style={{ animationDelay: `${520 + lane * 60}ms` }}
              />
            </g>
          );
        })}
        <text x={132} y={H - 6} fontSize={11} fill="var(--risk-4)" fontWeight={600}>
          one window
        </text>
      </svg>
    );
  }

  if (axis === "concentration") {
    const leaves = [30, 82, 134, 186, 238, 276];
    return (
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} aria-hidden>
        <rect
          x={128}
          y={16}
          width={44}
          height={44}
          rx={13}
          fill="var(--node-device)"
          className="fig-pop"
        />
        {leaves.map((x, i) => (
          <g key={i}>
            <line
              x1={150}
              y1={60}
              x2={x}
              y2={134}
              stroke="var(--node-device)"
              strokeWidth={1.6}
              opacity={0.45}
              className="fig-draw"
              style={{ ["--dash" as string]: "160", animationDelay: `${180 + i * 70}ms` }}
            />
            <circle
              cx={x}
              cy={142}
              r={9}
              fill="var(--accent)"
              className="fig-pop"
              style={{ animationDelay: `${420 + i * 70}ms` }}
            />
          </g>
        ))}
        <text x={0} y={178} fontSize={11} fill="var(--ink-3)">
          one attribute · six clients
        </text>
      </svg>
    );
  }

  const amounts = [58, 61, 59, 60, 58, 124, 60, 59];
  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} aria-hidden>
      <line x1={0} y1={156} x2={W} y2={156} stroke="var(--rule-strong)" strokeWidth={1} />
      {amounts.map((v, i) => (
        <rect
          key={i}
          x={8 + i * 36}
          y={156 - v}
          width={22}
          height={v}
          rx={5}
          fill={v > 90 ? "var(--rule-strong)" : "var(--risk-3)"}
          className="fig-grow"
          style={{ animationDelay: `${i * 70}ms` }}
        />
      ))}
      <text x={0} y={180} fontSize={11} fill="var(--ink-3)">
        seven at $25 · one outlier
      </text>
    </svg>
  );
}

/* --------------------------------------------------------------------- panel */

export function AxisAtlas() {
  const [selected, setSelected] = useState<AxisName>("synchrony");
  const axes = useQuery({ queryKey: queryKeys.axes(), queryFn: api.axes });

  const spec = SPECS[selected];
  const lift = axes.data?.axes[selected]?.enrichment;
  const beats = lift !== undefined && lift >= 1;

  return (
    <div className="atlas">
      {/* Selector. A vertical list rather than tabs, because each row also has
          to carry its measured lift -- which is the thing that makes this an
          atlas and not a feature grid. */}
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {AXIS_ORDER.map((axis) => {
          const active = axis === selected;
          const value = axes.data?.axes[axis]?.enrichment;
          const wins = value !== undefined && value >= 1;
          return (
            <button
              key={axis}
              onClick={() => setSelected(axis)}
              aria-pressed={active}
              style={{
                display: "grid",
                gridTemplateColumns: "minmax(0, 1fr) auto",
                alignItems: "center",
                gap: 12,
                textAlign: "left",
                padding: "14px 16px",
                borderRadius: 14,
                background: active ? "var(--paper-raised)" : "transparent",
                border: `1px solid ${active ? "var(--accent-wash-2)" : "transparent"}`,
                boxShadow: active ? "var(--lift-1)" : "none",
                transition: "background 220ms linear, border-color 220ms linear, box-shadow 220ms linear",
              }}
              onMouseEnter={(e) => {
                if (!active) e.currentTarget.style.background = "var(--paper-sunken)";
              }}
              onMouseLeave={(e) => {
                if (!active) e.currentTarget.style.background = "transparent";
              }}
            >
              <span style={{ minWidth: 0 }}>
                <span style={{ display: "block", fontSize: 16, fontWeight: 600, letterSpacing: "-0.02em" }}>
                  {SPECS[axis].title}
                </span>
                <span style={{ display: "block", fontSize: 12, color: "var(--ink-3)", marginTop: 1 }}>
                  {SPECS[axis].question}
                </span>
              </span>
              <span style={{ textAlign: "right" }}>
                <span
                  className="mono"
                  style={{ display: "block", fontSize: 15, fontWeight: 600, color: wins ? "var(--ink)" : "var(--ink-4)" }}
                >
                  {value === undefined ? "—" : `${value.toFixed(2)}×`}
                </span>
                {/* A two-pixel bar against the 1.00x control. It is the whole
                    ranking result, repeated four times, at a glance. */}
                <span
                  style={{
                    display: "block",
                    position: "relative",
                    width: 58,
                    height: 4,
                    marginTop: 5,
                    borderRadius: 999,
                    background: "var(--paper-sunken)",
                  }}
                >
                  <span
                    style={{
                      position: "absolute",
                      left: "50%",
                      top: -2,
                      width: 1,
                      height: 8,
                      background: "var(--rule-ink)",
                    }}
                  />
                  <span
                    style={{
                      display: "block",
                      width: `${Math.min(100, ((value ?? 0) / 2) * 100)}%`,
                      height: "100%",
                      borderRadius: 999,
                      background: wins ? "var(--risk-3)" : "var(--risk-0)",
                      transition: "width 700ms var(--ease-out)",
                    }}
                  />
                </span>
              </span>
            </button>
          );
        })}
      </div>

      {/* Keyed on the selection so the figure remounts and its entrance
          animation replays on every switch. */}
      <article key={selected} className="card atlas-panel">
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 20 }}>
          <div>
            <div className="caps">{spec.title}</div>
            <h3 style={{ margin: "6px 0 0", fontSize: 22, fontWeight: 600, letterSpacing: "-0.025em", color: "var(--accent)" }}>
              {spec.question}
            </h3>
          </div>
          <div style={{ textAlign: "right", flexShrink: 0 }}>
            <div className="mono" style={{ fontSize: 26, fontWeight: 600, letterSpacing: "-0.04em" }}>
              {lift === undefined ? "—" : `${lift.toFixed(2)}×`}
            </div>
            <div className="caps" style={{ color: beats ? "var(--risk-3)" : "var(--ink-4)" }}>
              {lift === undefined ? "measuring" : beats ? "beats the control" : "below the control"}
            </div>
          </div>
        </div>

        <div style={{ margin: "20px -4px 4px" }}>
          <Figure axis={selected} />
        </div>

        <p style={{ margin: "4px 0 0", fontSize: 14, lineHeight: 1.7, color: "var(--ink-2)" }}>{spec.definition}</p>

        <div
          className="mono"
          style={{
            marginTop: 16,
            padding: "11px 14px",
            borderRadius: 10,
            background: "var(--paper-sunken)",
            fontSize: 12.5,
            color: "var(--ink)",
          }}
        >
          {spec.formula}
        </div>

        <dl style={{ margin: "18px 0 0", display: "grid", gap: 12 }}>
          {[
            ["Fires on", spec.fires, "var(--risk-3)"],
            ["Blind to", spec.blind, "var(--ink-4)"],
          ].map(([label, text, colour]) => (
            <div key={label} style={{ display: "grid", gridTemplateColumns: "76px minmax(0, 1fr)", gap: 12 }}>
              <dt className="caps" style={{ color: colour, marginTop: 2 }}>
                {label}
              </dt>
              <dd style={{ margin: 0, fontSize: 13.5, lineHeight: 1.65, color: "var(--ink-2)" }}>{text}</dd>
            </div>
          ))}
        </dl>
      </article>
    </div>
  );
}
