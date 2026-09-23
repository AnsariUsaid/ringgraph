import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RingList } from "./panels/RingList";
import { GraphCanvas } from "./panels/GraphCanvas";
import { EvidencePanel } from "./panels/EvidencePanel";
import { ModelComparison } from "./panels/ModelComparison";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      // Keep the shell and the last good data on a backend hiccup rather than
      // blanking to white mid-demo.
      gcTime: 30 * 60 * 1000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

type View = "investigate" | "results";

const VIEWS: { key: View; label: string; hint: string }[] = [
  { key: "investigate", label: "Investigate", hint: "explore detected rings" },
  { key: "results", label: "Results", hint: "does structure add lift?" },
];

function Panel({ children, side }: { children: React.ReactNode; side: "left" | "right" }) {
  return (
    <div
      style={{
        background: "var(--bg-panel)",
        [side === "left" ? "borderRight" : "borderLeft"]: "1px solid var(--border-subtle)",
        display: "flex",
        flexDirection: "column",
        // Without this a flex/grid child refuses to shrink and grows the panel
        // off-screen. The most reliable layout bug in this shape.
        minHeight: 0,
        minWidth: 0,
      }}
    >
      {children}
    </div>
  );
}

/** Ring exploration: list drives canvas drives evidence. */
function Investigate() {
  const [sort, setSort] = useState("burst_share");
  return (
    <div
      style={{ display: "grid", gridTemplateColumns: "320px 1fr 400px", flex: 1, minHeight: 0 }}
    >
      <Panel side="left">
        <RingList sort={sort} onSortChange={setSort} />
      </Panel>
      <div style={{ minWidth: 0, minHeight: 0 }}>
        <GraphCanvas />
      </div>
      <Panel side="right">
        <EvidencePanel />
      </Panel>
    </div>
  );
}

function Workbench() {
  const [view, setView] = useState<View>("investigate");

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", minHeight: 0 }}>
      <header
        style={{
          height: 52,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 16px",
          borderBottom: "1px solid var(--border-subtle)",
          background: "var(--bg-app)",
          boxShadow: "inset 0 1px 0 rgba(255,255,255,0.04)",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
          <span style={{ fontSize: 15, fontWeight: 600 }}>Relational Fraud Intelligence</span>
          <span style={{ fontSize: 11, color: "var(--fg-muted)" }}>
            {VIEWS.find((v) => v.key === view)?.hint}
          </span>
        </div>
        {/* Two views rather than a tab inside the evidence panel: the model
            comparison shares no state with the graph and needs the full width
            for its intervals. */}
        <nav style={{ display: "flex", gap: 2 }}>
          {VIEWS.map((option) => (
            <button
              key={option.key}
              onClick={() => setView(option.key)}
              aria-current={view === option.key}
              style={{
                fontSize: 12,
                padding: "5px 12px",
                borderRadius: "var(--radius-control)",
                color: view === option.key ? "var(--accent)" : "var(--fg-secondary)",
                background: view === option.key ? "var(--accent-muted)" : "transparent",
                border: `1px solid ${view === option.key ? "var(--accent)" : "transparent"}`,
              }}
            >
              {option.label}
            </button>
          ))}
        </nav>
      </header>

      {view === "investigate" ? (
        <Investigate />
      ) : (
        <div className="scroll" style={{ flex: 1, minHeight: 0 }}>
          <ModelComparison />
        </div>
      )}
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Workbench />
    </QueryClientProvider>
  );
}
