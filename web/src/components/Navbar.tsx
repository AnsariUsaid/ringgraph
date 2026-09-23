import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { View } from "../views";

interface Props {
  view: View;
  onChange: (view: View) => void;
  items: { key: View; label: string }[];
}

/** Floating navigation with a sliding indicator.
 *
 * The indicator is one element that moves, rather than a background that
 * appears and disappears per button. That is the whole difference between a nav
 * that feels built and one that feels defaulted: the eye tracks a single object
 * across the bar instead of watching two things blink.
 *
 * Positions are measured from the DOM rather than assumed, so the labels can
 * change length without the geometry being re-tuned by hand.
 */
export function Navbar({ view, onChange, items }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const buttonRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const [indicator, setIndicator] = useState({ left: 0, width: 0 });
  const [hovered, setHovered] = useState<View | null>(null);
  const [ready, setReady] = useState(false);

  const target = hovered ?? view;

  useLayoutEffect(() => {
    const button = buttonRefs.current[target];
    const container = containerRef.current;
    if (!button || !container) return;
    const b = button.getBoundingClientRect();
    const c = container.getBoundingClientRect();
    setIndicator({ left: b.left - c.left, width: b.width });
  }, [target, items]);

  // Skip the transition on first paint, or the indicator visibly slides in
  // from the left edge on load.
  useEffect(() => {
    const id = requestAnimationFrame(() => setReady(true));
    return () => cancelAnimationFrame(id);
  }, []);

  const isHoverPreview = hovered !== null && hovered !== view;

  return (
    <nav
      ref={containerRef}
      onMouseLeave={() => setHovered(null)}
      className="edge-lit"
      style={{
        position: "fixed",
        top: 18,
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 50,
        display: "flex",
        alignItems: "center",
        gap: 6,
        padding: "6px 8px 6px 6px",
        borderRadius: 999,
        background: "rgba(9, 15, 28, 0.9)",
        border: "1px solid rgba(255,255,255,0.07)",
        backdropFilter: "blur(20px) saturate(150%)",
        WebkitBackdropFilter: "blur(20px) saturate(150%)",
        boxShadow: "0 18px 50px -18px rgba(0,0,0,0.9), 0 2px 10px -4px rgba(0,0,0,0.6)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 9,
          padding: "0 16px 0 12px",
          borderRight: "1px solid rgba(255,255,255,0.07)",
          marginRight: 4,
          alignSelf: "stretch",
        }}
      >
        <span
          aria-hidden
          style={{
            width: 9,
            height: 9,
            borderRadius: 3,
            background: "var(--grad-signature)",
            boxShadow: "0 0 14px rgba(200,247,81,0.6)",
          }}
        />
        <span
          className="mono"
          style={{
            fontSize: 11.5,
            letterSpacing: "0.14em",
            color: "var(--fg-secondary)",
            textTransform: "uppercase",
            whiteSpace: "nowrap",
          }}
        >
          Fraud Intelligence
        </span>
      </div>

      {/* One indicator, moving. */}
      <div
        aria-hidden
        style={{
          position: "absolute",
          left: indicator.left,
          width: indicator.width,
          top: 6,
          bottom: 6,
          borderRadius: 999,
          background: isHoverPreview ? "rgba(255,255,255,0.07)" : "rgba(255,255,255,0.1)",
          border: `1px solid ${isHoverPreview ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.14)"}`,
          boxShadow: isHoverPreview ? "none" : "inset 0 1px 0 rgba(255,255,255,0.1)",
          transition: ready
            ? "left 420ms var(--ease-spring), width 420ms var(--ease-spring), background 200ms var(--ease-out), border-color 200ms var(--ease-out)"
            : "none",
        }}
      />

      {items.map((item) => {
        const active = item.key === view;
        return (
          <button
            key={item.key}
            ref={(el) => {
              buttonRefs.current[item.key] = el;
            }}
            onClick={() => onChange(item.key)}
            onMouseEnter={() => setHovered(item.key)}
            onFocus={() => setHovered(item.key)}
            onBlur={() => setHovered(null)}
            aria-current={active}
            style={{
              position: "relative",
              zIndex: 1,
              fontSize: 13,
              fontWeight: 500,
              padding: "9px 20px",
              borderRadius: 999,
              whiteSpace: "nowrap",
              color: active ? "var(--fg-primary)" : "var(--fg-secondary)",
              transition: "color 200ms var(--ease-out)",
            }}
          >
            {item.label}
          </button>
        );
      })}
    </nav>
  );
}
