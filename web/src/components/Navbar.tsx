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
  const [ripple, setRipple] = useState<{ id: number; x: number; y: number } | null>(null);

  const target = hovered ?? active;
  // The indicator is dark ink when it sits on the committed route and a light
  // wash when it is previewing a hover. Labels may only invert under the dark
  // one -- previously "active" alone decided it, so hovering a *different*
  // item slid the dark pill away and left the active label white on paper,
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
          gap: 6,
          padding: "10px 11px 10px 24px",
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
          style={{ display: "flex", alignItems: "center", gap: 12, paddingRight: 18 }}
        >
          <Mark size={30} />
          <span
            className="nav-wordmark"
            style={{
              fontSize: 19,
              fontWeight: 600,
              letterSpacing: "-0.03em",
              whiteSpace: "nowrap",
            }}
          >
            Ring<span style={{ color: "var(--ink-3)" }}>graph</span>
          </span>
        </Link>

        <span style={{ width: 1, height: 32, background: "var(--rule)", marginRight: 8 }} />

        <div ref={listRef} style={{ position: "relative", display: "flex", gap: 4 }} onMouseLeave={() => setHovered(null)}>
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
                background: previewing ? "var(--accent-wash)" : "var(--ink)",
                // Translating a fixed-origin element rather than animating
                // `left` keeps this on the compositor.
                transform: `translate3d(${box.x}px, 0, 0)`,
                transition:
                  "transform 480ms var(--ease-spring), width 480ms var(--ease-spring), background 240ms linear",
                pointerEvents: "none",
              }}
            />
          )}

          {ripple && (
            <span
              key={ripple.id}
              aria-hidden
              onAnimationEnd={() => setRipple(null)}
              style={{
                position: "absolute",
                left: ripple.x - 62,
                top: ripple.y - 62,
                width: 124,
                height: 124,
                borderRadius: "50%",
                background: "var(--accent)",
                animation: "ripple 620ms var(--ease-out) forwards",
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
                onClick={(event) => {
                  const rect = listRef.current?.getBoundingClientRect();
                  if (rect) {
                    setRipple({ id: Date.now(), x: event.clientX - rect.left, y: event.clientY - rect.top });
                  }
                }}
                style={{
                  position: "relative",
                  padding: "15px 26px",
                  borderRadius: 999,
                  fontSize: 16.5,
                  fontWeight: 500,
                  whiteSpace: "nowrap",
                  // Three states, all legible: the committed route inverts to
                  // paper under the dark pill; while a hover is previewing, the
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
