import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link, ROUTES, useRouter, type Route } from "../router";
import { Mark } from "./Mark";

const ITEMS: { to: Route; label: string; hint: string }[] = [
  { to: "/", label: "Overview", hint: "What the system looks for" },
  { to: "/explore", label: "Explore", hint: "550 candidate rings" },
  { to: "/results", label: "Results", hint: "Did structure help?" },
];

/** Floating pill navigation.
 *
 * The indicator is one absolutely-positioned element whose x and width are
 * *measured from the DOM* rather than derived from assumed item widths -- the
 * labels are different lengths and the font may still be swapping in when the
 * bar first paints, so any computed guess is wrong for the first frame and
 * stays wrong on a font fallback. It animates on a spring curve, which is what
 * makes the bar feel like a physical object instead of a highlight jumping
 * between buttons.
 *
 * It also follows the pointer on hover and springs back on leave, so the bar
 * answers before you commit.
 */
export function Navbar() {
  const { route, pending, navigate } = useRouter();
  const active = pending ?? route;

  const listRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef(new Map<Route, HTMLAnchorElement>());
  const [hovered, setHovered] = useState<Route | null>(null);
  const [box, setBox] = useState<{ x: number; w: number } | null>(null);
  const [scrolled, setScrolled] = useState(false);

  const target = hovered ?? active;
  // The indicator is solid accent when it sits on the committed route and a light
  // wash when it is previewing a hover. Labels may only invert under the solid
  // one -- previously "active" alone decided it, so hovering a *different*
  // item slid the solid pill away and left the active label white on paper,
  // invisible until the pointer came back.
  const previewing = hovered !== null && hovered !== active;

  // Layout effect, not effect: measuring after paint would show the indicator
  // at its old position for one frame on every route change.
  useLayoutEffect(() => {
    const node = itemRefs.current.get(target);
    if (!node) return;
    setBox({ x: node.offsetLeft, w: node.offsetWidth });
  }, [target]);

  // Labels reflow when the webfont lands and when the window resizes, and a
  // stale indicator is the most visible possible bug on this component.
  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const remeasure = () => {
      const node = itemRefs.current.get(target);
      if (node) setBox({ x: node.offsetLeft, w: node.offsetWidth });
    };
    const observer = new ResizeObserver(remeasure);
    observer.observe(list);
    document.fonts?.ready.then(remeasure).catch(() => {});
    return () => observer.disconnect();
  }, [target]);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Keyboard parity with the pointer: the nav is three items, so arrow keys are
  // cheaper than tabbing and a reader who found the bar expects them to work.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!event.altKey) return;
      const index = ROUTES.indexOf(active);
      if (event.key === "ArrowRight") navigate(ROUTES[(index + 1) % ROUTES.length]);
      if (event.key === "ArrowLeft") navigate(ROUTES[(index + ROUTES.length - 1) % ROUTES.length]);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active, navigate]);

  return (
    <nav
      aria-label="Primary"
      style={{
        position: "fixed",
        top: scrolled ? 14 : 24,
        left: "50%",
        zIndex: 60,
        transform: "translateX(-50%)",
        transition: "top 420ms var(--ease-out)",
      }}
    >
      <div
        className="nav-shell"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "7px 9px 7px 30px",
          borderRadius: 999,
          border: "1px solid var(--rule)",
          // Glass, but tinted toward the paper rather than white, so the bar
          // stays warm against the page instead of reading as a grey plate.
          background: "rgba(252, 250, 246, 0.78)",
          backdropFilter: "blur(20px) saturate(180%)",
          WebkitBackdropFilter: "blur(20px) saturate(180%)",
          boxShadow: scrolled ? "var(--lift-3)" : "var(--lift-2)",
          transition: "box-shadow 420ms var(--ease-out)",
        }}
      >
        <Link
          to="/"
          aria-label="Relational Fraud Intelligence, overview"
          className="nav-brand"
          style={{ display: "flex", alignItems: "center", gap: 11, paddingRight: 34 }}
        >
          <Mark size={26} />
          <span
            className="nav-wordmark"
            style={{
              fontSize: 17,
              fontWeight: 600,
              letterSpacing: "-0.03em",
              whiteSpace: "nowrap",
            }}
          >
            Ring<span style={{ color: "var(--ink-3)" }}>graph</span>
          </span>
        </Link>

        <span className="nav-divider" style={{ width: 1, height: 24, background: "var(--rule)", marginRight: 18 }} />

        <div ref={listRef} style={{ position: "relative", display: "flex", gap: 6 }} onMouseLeave={() => setHovered(null)}>
          {box && (
            <span
              aria-hidden
              style={{
                position: "absolute",
                left: 0,
                top: 0,
                bottom: 0,
                width: box.w,
                borderRadius: 999,
                background: previewing ? "var(--accent-wash)" : "var(--accent)",
                // Translating a fixed-origin element rather than animating
                // `left` keeps this on the compositor.
                transform: `translate3d(${box.x}px, 0, 0)`,
                transition:
                  "transform 480ms var(--ease-spring), width 480ms var(--ease-spring), background 240ms linear",
                pointerEvents: "none",
              }}
            />
          )}

          {ITEMS.map((item) => {
            const isActive = item.to === active;
            const inverted = !previewing && item.to === target;
            return (
              <Link
                key={item.to}
                to={item.to}
                title={item.hint}
                aria-current={isActive ? "page" : undefined}
                className="nav-item"
                ref={(node: HTMLAnchorElement | null) => {
                  if (node) itemRefs.current.set(item.to, node);
                  else itemRefs.current.delete(item.to);
                }}
                onMouseEnter={() => setHovered(item.to)}
                style={{
                  position: "relative",
                  padding: "10px 52px",
                  borderRadius: 999,
                  fontSize: 15.5,
                  fontWeight: 500,
                  whiteSpace: "nowrap",
                  // Three states, all legible: the committed route inverts to
                  // paper under the accent pill; while a hover is previewing, the
                  // committed route keeps the accent ("you are here") and the
                  // previewed one goes full ink on its wash, so the two are
                  // never the same colour at the same time.
                  color: inverted
                    ? "var(--paper-raised)"
                    : isActive
                      ? "var(--accent)"
                      : item.to === hovered
                        ? "var(--ink)"
                        : "var(--ink-2)",
                  transition: "color 220ms linear",
                }}
              >
                {item.label}
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
