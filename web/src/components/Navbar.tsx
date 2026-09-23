import type { View } from "../views";

interface Props {
  view: View;
  onChange: (view: View) => void;
  items: { key: View; label: string }[];
}

/** Floating pill navigation.
 *
 * Fixed rather than in flow, so the workbench below keeps the full viewport
 * height — the canvas needs it. Backdrop blur rather than an opaque fill so the
 * graph stays faintly visible underneath and the bar reads as floating above
 * the work rather than as a band cut out of it.
 */
export function Navbar({ view, onChange, items }: Props) {
  return (
    <nav
      style={{
        position: "fixed",
        top: 14,
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 50,
        display: "flex",
        alignItems: "center",
        gap: 4,
        padding: 4,
        borderRadius: 999,
        // Opaque enough that content scrolling underneath reads as *behind* it
        // rather than through it -- at 0.72 the text bled and looked unfinished.
        background: "rgba(18, 23, 31, 0.93)",
        border: "1px solid var(--border-default)",
        backdropFilter: "blur(18px) saturate(140%)",
        WebkitBackdropFilter: "blur(18px) saturate(140%)",
        boxShadow: "var(--shadow-float)",
      }}
    >
      <span
        className="mono"
        style={{
          fontSize: 11,
          letterSpacing: "0.08em",
          color: "var(--fg-muted)",
          padding: "0 12px 0 14px",
          textTransform: "uppercase",
        }}
      >
        RFI
      </span>
      {items.map((item) => {
        const active = item.key === view;
        return (
          <button
            key={item.key}
            onClick={() => onChange(item.key)}
            aria-current={active}
            style={{
              position: "relative",
              fontSize: 12.5,
              fontWeight: 500,
              padding: "7px 16px",
              borderRadius: 999,
              color: active ? "var(--bg-canvas)" : "var(--fg-secondary)",
              background: active ? "var(--fg-primary)" : "transparent",
              transition:
                "background var(--dur-base) var(--ease-out), color var(--dur-base) var(--ease-out)",
            }}
            onMouseEnter={(e) => {
              if (!active) e.currentTarget.style.background = "rgba(255,255,255,0.06)";
            }}
            onMouseLeave={(e) => {
              if (!active) e.currentTarget.style.background = "transparent";
            }}
          >
            {item.label}
          </button>
        );
      })}
    </nav>
  );
}
