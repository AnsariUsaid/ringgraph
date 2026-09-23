import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Navbar } from "./components/Navbar";
import { RingList } from "./panels/RingList";
import { GraphCanvas } from "./panels/GraphCanvas";
import { EvidencePanel } from "./panels/EvidencePanel";
import { ModelComparison } from "./panels/ModelComparison";
import { Landing } from "./panels/Landing";
import { VIEWS, type View } from "./views";

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

/** Ring exploration: list drives canvas drives evidence.
 *
 * Takes the full viewport height with the navbar floating over it, because the
 * canvas is the one thing here that genuinely benefits from every pixel.
 */
function Investigate() {
  const [sort, setSort] = useState("burst_share");
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "320px minmax(0, 1fr) 400px",
        height: "100vh",
        minHeight: 0,
      }}
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

function Shell() {
  const [view, setView] = useState<View>("overview");

  const navigate = (next: View) => {
    setView(next);
    window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
  };

  return (
    <>
      <Navbar view={view} onChange={navigate} items={VIEWS} />
      {/* Keyed so each view re-enters rather than swapping in place. */}
      <main key={view} style={{ animation: "fade var(--dur-base) var(--ease-out)" }}>
        {view === "overview" && <Landing onNavigate={navigate} />}
        {view === "investigate" && <Investigate />}
        {view === "results" && <ModelComparison />}
      </main>
    </>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Shell />
    </QueryClientProvider>
  );
}
