import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

/** A ~90-line router, deliberately not react-router.
 *
 * Three static routes, no params, no nesting, no data loaders. What this app
 * actually needs that a library would not give for free is a *two-phase*
 * navigation: the outgoing page has to finish animating out before the
 * incoming one mounts, or the transition is a cross-fade of two pages fighting
 * over the same scroll position. So the exit delay lives in the router rather
 * than being bolted onto it from a wrapper.
 */

export const ROUTES = ["/", "/explore", "/results"] as const;
export type Route = (typeof ROUTES)[number];

/** How long the exit animation runs before the next page mounts. Matches the
 *  `page-out` keyframe; the wipe covers the swap itself. */
const EXIT_MS = 190;

function normalise(pathname: string): Route {
  const trimmed = pathname.replace(/\/+$/, "") || "/";
  return (ROUTES as readonly string[]).includes(trimmed) ? (trimmed as Route) : "/";
}

interface RouterValue {
  route: Route;
  /** The route being animated *to*, or null when settled. Nav highlights read
   *  this so the indicator commits the moment you click, not 190ms later. */
  pending: Route | null;
  phase: "in" | "out";
  navigate: (to: Route) => void;
}

const RouterContext = createContext<RouterValue | null>(null);

export function RouterProvider({ children }: { children: React.ReactNode }) {
  const [route, setRoute] = useState<Route>(() => normalise(window.location.pathname));
  const [pending, setPending] = useState<Route | null>(null);
  const [phase, setPhase] = useState<"in" | "out">("in");
  const timer = useRef<number | undefined>(undefined);

  // Committing is shared by clicks and by the back button, which differ only in
  // whether a history entry is pushed.
  const commit = useCallback((to: Route, push: boolean) => {
    window.clearTimeout(timer.current);
    setPending(to);
    setPhase("out");
    timer.current = window.setTimeout(() => {
      if (push) window.history.pushState({}, "", to);
      setRoute(to);
      setPending(null);
      setPhase("in");
      // The workbench manages its own scroll; the scrolling pages must start at
      // the top or a deep-scrolled Results page opens Overview at its footer.
      window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
    }, EXIT_MS);
  }, []);

  const navigate = useCallback(
    (to: Route) => {
      if (to === route && !pending) return;
      commit(to, true);
    },
    [commit, route, pending],
  );

  useEffect(() => {
    const onPop = () => commit(normalise(window.location.pathname), false);
    window.addEventListener("popstate", onPop);
    return () => {
      window.removeEventListener("popstate", onPop);
      window.clearTimeout(timer.current);
    };
  }, [commit]);

  const value = useMemo(() => ({ route, pending, phase, navigate }), [route, pending, phase, navigate]);
  return <RouterContext.Provider value={value}>{children}</RouterContext.Provider>;
}

export function useRouter(): RouterValue {
  const value = useContext(RouterContext);
  if (!value) throw new Error("useRouter must be used inside RouterProvider");
  return value;
}

/** A real anchor, so the link has a URL, opens in a new tab on cmd-click, and
 *  shows a destination in the status bar. Only plain left clicks are
 *  intercepted. */
export function Link({
  to,
  children,
  ref,
  ...rest
}: { to: Route; children: React.ReactNode; ref?: React.Ref<HTMLAnchorElement> } & Omit<
  React.AnchorHTMLAttributes<HTMLAnchorElement>,
  "href" | "ref"
>) {
  const { navigate } = useRouter();
  return (
    <a
      ref={ref}
      href={to}
      onClick={(event) => {
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
        event.preventDefault();
        navigate(to);
        rest.onClick?.(event);
      }}
      {...rest}
    >
      {children}
    </a>
  );
}
