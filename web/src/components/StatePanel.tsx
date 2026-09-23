interface Props {
  title: string;
  body?: string;
  tone?: "neutral" | "error";
}

/** One component for every empty, loading-failed and unreachable state.
 *
 * Enumerated up front rather than added when each one is hit: an afterthought
 * empty state is where a demo looks unfinished. Errors are not red -- red is
 * reserved for risk. */
export function StatePanel({ title, body, tone = "neutral" }: Props) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        padding: 28,
        textAlign: "center",
        gap: 8,
      }}
    >
      <svg width="36" height="36" viewBox="0 0 36 36" aria-hidden style={{ marginBottom: 2 }}>
        <circle cx="18" cy="18" r="13" fill="none" stroke="var(--rule-strong)" strokeWidth="1.5" strokeDasharray="3 5" />
        <circle cx="18" cy="18" r="3.5" fill={tone === "error" ? "var(--risk-3)" : "var(--rule-ink)"} />
      </svg>
      <div style={{ fontSize: 14.5, fontWeight: 600, color: "var(--ink-2)" }}>{title}</div>
      {body && (
        <div style={{ fontSize: 12.5, color: "var(--ink-3)", maxWidth: 300, lineHeight: 1.6 }}>{body}</div>
      )}
      {tone === "error" && (
        <div
          className="mono"
          style={{
            fontSize: 11,
            color: "var(--ink-3)",
            marginTop: 6,
            padding: "4px 10px",
            borderRadius: 999,
            background: "var(--paper-sunken)",
          }}
        >
          is the API running on :8000?
        </div>
      )}
    </div>
  );
}
