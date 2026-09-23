import { useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Navbar } from "./components/Navbar";
import { Landing } from "./pages/Landing";
import { Explore } from "./pages/Explore";
import { Results } from "./pages/Results";
import { RouterProvider, useRouter } from "./router";

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

/** The accent bar that crosses the viewport once per navigation.
 *
 * Keyed on the pending route so it restarts on every click, including a click
 * on the route you are already leaving. It is the thing that makes the swap
 * feel intentional rather than like a flash of unstyled content.
 */
function RouteWipe({ token }: { token: string | null }) {
  if (!token) return null;
  return (
    <span
      key={token}
      aria-hidden
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        height: 3,
        zIndex: 80,
        background: "linear-gradient(90deg, var(--accent), var(--risk-3), var(--risk-4))",
        animation: "wipe 620ms var(--ease-out) forwards",
      }}
    />
  );
}

function Pages() {
  const { route, pending, phase } = useRouter();

  // The workbench owns the viewport; the other two routes scroll. Toggling
  // this on the body rather than on a wrapper is what stops the window
  // scrollbar appearing and shifting the fixed nav by 11px on every
  // navigation into Explore.
  //
  // Only above the breakpoint, though: below it the three columns stack into a
  // taller-than-viewport page, and locking the body there makes everything
  // under the first panel unreachable. The query has to be *live*, not read
  // once -- resizing across the breakpoint while on Explore hits exactly that
  // bug otherwise.
  useEffect(() => {
    if (route !== "/explore") {
      document.body.style.overflow = "";
      return;
    }
    const query = window.matchMedia("(min-width: 1121px)");
    const apply = () => {
      document.body.style.overflow = query.matches ? "hidden" : "";
    };
    apply();
    query.addEventListener("change", apply);
    return () => {
      query.removeEventListener("change", apply);
      document.body.style.overflow = "";
    };
  }, [route]);

  return (
    <>
      <RouteWipe token={pending} />
      <main
        // Keyed on the route so React remounts rather than reconciles: two
        // pages this different share nothing, and reconciling them would keep
        // scroll positions and half-finished animations across the swap.
        key={route}
        style={{
          animation:
            phase === "out"
              ? "page-out 190ms var(--ease-out) forwards"
              : "page-in 420ms var(--ease-out) both",
        }}
      >
        {route === "/" && <Landing />}
        {route === "/explore" && <Explore />}
        {route === "/results" && <Results />}
      </main>
    </>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider>
        <Navbar />
        <Pages />
      </RouterProvider>
    </QueryClientProvider>
  );
}
