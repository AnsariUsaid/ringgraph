import { useEffect, useRef, useState } from "react";
import { CountUp } from "./CountUp";

interface Stage {
  script: string;
  title: string;
  body: string;
  figure: { value: number; decimals?: number; suffix?: string; prefix?: string; unit: string };
  /** Gates are the two steps that could have ended the project. They are
   *  marked because a pipeline diagram that shows only the happy path is a
   *  sales diagram. */
  gate?: boolean;
}

/** The real pipeline, in the order README.md runs it, with the figure each
 *  step actually produced. Every number here is read off a committed report
 *  in reports/ or a parquet manifest -- none of them are illustrative. */
const STAGES: Stage[] = [
  {
    script: "10_ingest",
    title: "Ingest",
    body: "Join the transaction table to the identity table, fix dtypes, derive a day index. Identity attributes — device, screen, OS, browser — reach only a quarter of the rows, and everything downstream is built on that quarter.",
    figure: { value: 590540, unit: "rows × 436 columns" },
  },
  {
    script: "30_uid_map",
    title: "Resolve",
    body: "Collapse rows into clients on card, address and normalised first-seen day. Three recipes are kept and all conclusions are re-checked against each, because entity resolution is the assumption most likely to be quietly wrong.",
    figure: { value: 217850, unit: "clients · 57% singletons" },
  },
  {
    script: "40_label_homogeneity",
    title: "Gate: is there a signal?",
    body: "Before building a graph, ask whether shared attributes carry ring signal at all. Groups sharing card1 contain 650 fraud-bearing pairs against 950 expected by chance — 17 sd below the null. Hub attributes are anti-predictive, which is what caps the degree band.",
    figure: { value: -17.5, decimals: 1, suffix: " sd", unit: "below the null, on card1" },
    gate: true,
  },
  {
    script: "50_synchrony",
    title: "Gate: do they coordinate?",
    body: "The gate the project actually had to pass. Do linked clients transact in the same window more than unlinked ones? In the smallest size band, candidate components produce 88 same-window bursts against a null expectation of 0.2.",
    figure: { value: 391, unit: "× the null burst rate" },
    gate: true,
  },
  {
    script: "48_percolation",
    title: "Project",
    body: "Percolation picks the degree band and weight floor — low enough to keep real links, high enough that one shared browser string does not merge the population into a single blob. Band 2–10, weight floor 1.",
    figure: { value: 13460, unit: "links over 4,762 clients" },
  },
  {
    script: "95_ring_catalogue",
    title: "Catalogue",
    body: "Components become rings, scored on four axes plus burst share, and written to parquet so the API is a dataframe filter rather than a graph traversal. Median ring is 5 clients; the largest is 165.",
    figure: { value: 550, unit: "rings · 917 confirmed fraud" },
  },
  {
    script: "91_multiseed",
    title: "Compare",
    body: "Two models, identical but for the graph features, five seeds each, paired on training randomness. Seed-only variation turns out larger than any difference between the models, and every interval spans zero.",
    figure: { value: 5, unit: "seeds · 3 of 3 intervals span 0" },
  },
];

/** The pipeline as a rail rather than a row of cards.
 *
 * Cards made seven unequal steps look like seven equal ones, and they were
 * small enough to read as a footnote to the page. A rail gives the sequence a
 * direction, gives each step room for the figure it produced, and lets the two
 * *gates* be marked as what they are: the points where the project could have
 * stopped.
 *
 * The rail fills as steps come into view and a packet travels the filled part,
 * so the section is visibly a pipeline and not a list.
 */
export function Pipeline() {
  const [reached, setReached] = useState(0);
  const railRef = useRef<HTMLDivElement>(null);
  const [railHeight, setRailHeight] = useState(0);

  // The travelling packet animates by a pixel distance, so it has to be
  // measured rather than expressed as a percentage -- `translateY(100%)` on a
  // 10px dot moves it 10px.
  useEffect(() => {
    const rail = railRef.current;
    if (!rail) return;
    const observer = new ResizeObserver(() => setRailHeight(rail.offsetHeight));
    observer.observe(rail);
    setRailHeight(rail.offsetHeight);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={railRef} style={{ position: "relative" }}>
      {/* Rail: an unfilled track, the filled portion, and the packet. All
          three are one column so the stages can sit in a normal grid. */}
      <div
        aria-hidden
        style={{ position: "absolute", left: 21, top: 30, bottom: 30, width: 2, background: "var(--rule)" }}
      >
        <div
          style={{
            width: "100%",
            height: `${(reached / STAGES.length) * 100}%`,
            background: "linear-gradient(var(--accent), var(--risk-3))",
            transition: "height 900ms var(--ease-out)",
          }}
        />
        {reached > 0 && railHeight > 0 && (
          <span
            style={{
              position: "absolute",
              left: -3,
              top: 0,
              width: 8,
              height: 8,
              borderRadius: 999,
              background: "var(--accent)",
              boxShadow: "0 0 0 4px var(--accent-wash)",
              ["--travel" as string]: `${Math.max(0, railHeight - 60)}px`,
              animation: "travel 4.2s linear infinite",
            }}
          />
        )}
      </div>

      <ol style={{ listStyle: "none", margin: 0, padding: 0 }}>
        {STAGES.map((stage, index) => (
          <Step key={stage.script} stage={stage} index={index} onEnter={() => setReached((n) => Math.max(n, index + 1))} />
        ))}
      </ol>
    </div>
  );
}

function Step({ stage, index, onEnter }: { stage: Stage; index: number; onEnter: () => void }) {
  const [node, setNode] = useState<HTMLLIElement | null>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    if (!node) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        setShown(true);
        onEnter();
        observer.disconnect();
      },
      { rootMargin: "0px 0px -18% 0px", threshold: 0.1 },
    );
    observer.observe(node);
    return () => observer.disconnect();
    // `onEnter` is a fresh closure each render; depending on it would tear the
    // observer down and rebuild it on every parent state change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [node]);

  return (
    <li
      ref={setNode}
      className="pipeline-step"
      style={{
        opacity: shown ? 1 : 0,
        transform: shown ? "none" : "translate3d(0, 20px, 0)",
        transition: "opacity 620ms var(--ease-out), transform 620ms var(--ease-out)",
      }}
    >
      {/* Node on the rail. Gates get the risk colour and a ring, because they
          are decision points rather than transformations. */}
      <div style={{ position: "relative", width: 44, flexShrink: 0 }}>
        <span
          style={{
            position: "absolute",
            left: 14,
            top: 4,
            width: 16,
            height: 16,
            borderRadius: 999,
            background: shown ? (stage.gate ? "var(--risk-4)" : "var(--accent)") : "var(--rule-strong)",
            boxShadow: `0 0 0 5px var(--paper)`,
            transition: "background 500ms var(--ease-out)",
          }}
        />
        {shown && stage.gate && (
          <span
            aria-hidden
            style={{
              position: "absolute",
              left: 14,
              top: 4,
              width: 16,
              height: 16,
              borderRadius: 999,
              border: "2px solid var(--risk-4)",
              animation: "pulse-ring 2.4s var(--ease-out) infinite",
            }}
          />
        )}
      </div>

      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
          <span className="mono" style={{ fontSize: 11, color: "var(--ink-4)" }}>
            {String(index + 1).padStart(2, "0")}
          </span>
          <h3 style={{ margin: 0, fontSize: 21, fontWeight: 600, letterSpacing: "-0.025em" }}>{stage.title}</h3>
          <code
            className="mono"
            style={{
              fontSize: 10.5,
              padding: "3px 9px",
              borderRadius: 999,
              color: stage.gate ? "var(--risk-4)" : "var(--ink-3)",
              background: stage.gate ? "var(--risk-4-wash)" : "var(--paper-sunken)",
            }}
          >
            {stage.script}.py
          </code>
        </div>
        <p style={{ margin: "9px 0 0", fontSize: 14, lineHeight: 1.7, color: "var(--ink-2)", maxWidth: 620 }}>
          {stage.body}
        </p>
      </div>

      <div className="pipeline-figure">
        <div style={{ fontSize: 30, fontWeight: 600, letterSpacing: "-0.04em", lineHeight: 1.1 }}>
          {shown ? (
            <CountUp
              to={stage.figure.value}
              decimals={stage.figure.decimals ?? 0}
              prefix={stage.figure.prefix ?? ""}
              suffix={stage.figure.suffix ?? ""}
            />
          ) : (
            <span className="mono">—</span>
          )}
        </div>
        <div className="caps" style={{ marginTop: 4, lineHeight: 1.4 }}>
          {stage.figure.unit}
        </div>
      </div>
    </li>
  );
}
