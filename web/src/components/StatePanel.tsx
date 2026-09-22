interface Props {
  title: string;
  body?: string;
  tone?: "neutral" | "error";
}

/** One component for every empty, loading-failed and unreachable state.
 *
 * Enumerated up front rather than added when each one is hit: an afterthought
 * empty state is where a demo looks unfinished. Errors are not red -- red is
 * reserved for risk (D-28). */
export function StatePanel({ title, body, tone = "neutral" }: Props) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        padding: 24,
        textAlign: "center",
        gap: 6,
      }}
    >
      <div style={{ fontSize: 14, fontWeight: 500, color: "var(--fg-secondary)" }}>{title}</div>
      {body && (
        <div style={{ fontSize: 12, color: "var(--fg-muted)", maxWidth: 320, lineHeight: 1.6 }}>
          {body}
        </div>
      )}
      {tone === "error" && (
        <div className="mono" style={{ fontSize: 11, color: "var(--fg-muted)", marginTop: 4 }}>
          is the API running on :8000?
        </div>
      )}
    </div>
  );
}
