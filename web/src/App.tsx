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

function Panel({ children, right = false }: { children: React.ReactNode; right?: boolean }) {
  return (
    <div
      style={{
        background: "var(--bg-panel)",
        borderLeft: right ? "1px solid var(--border-subtle)" : undefined,
        borderRight: right ? undefined : "1px solid var(--border-subtle)",
        display: "flex",
        flexDirection: "column",
        // Without this a flex/grid child refuses to shrink and grows the panel
        // off-screen. It is the single most reliable layout bug in this shape.
        minHeight: 0,
        minWidth: 0,
      }}
    >
      {children}
    </div>
  );
}

function Workbench() {
  const [sort, setSort] = useState("composite");
  const [tab, setTab] = useState<"evidence" | "models">("evidence");

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
            coordinated ring detection via shared-device structure
          </span>
        </div>
        <div style={{ display: "flex", gap: 2 }}>
          {(["evidence", "models"] as const).map((key) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              style={{
                fontSize: 11,
                padding: "4px 10px",
                borderRadius: "var(--radius-control)",
                color: tab === key ? "var(--accent)" : "var(--fg-muted)",
                background: tab === key ? "var(--accent-muted)" : "transparent",
                border: `1px solid ${tab === key ? "var(--accent)" : "transparent"}`,
              }}
            >
              {key === "evidence" ? "Evidence" : "Model comparison"}
            </button>
          ))}
        </div>
      </header>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "320px 1fr 400px",
          flex: 1,
          minHeight: 0,
        }}
      >
        <Panel>
          <RingList sort={sort} onSortChange={setSort} />
        </Panel>
        <div style={{ minWidth: 0, minHeight: 0 }}>
          <GraphCanvas />
        </div>
        <Panel right>{tab === "evidence" ? <EvidencePanel /> : <ModelComparison />}</Panel>
      </div>
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
