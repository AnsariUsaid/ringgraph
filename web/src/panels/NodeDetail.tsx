import type { CyElement, RingDetail } from "../api/types";
import { formatAmount, truncateId } from "../lib/risk";
import { useSelection } from "../store/selection";

interface Props {
  nodeId: string;
  ring: RingDetail;
  elements: CyElement[];
}

function Row({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, fontSize: 11 }}>
      <span style={{ color: "var(--fg-muted)" }}>{label}</span>
      <span className="mono" style={{ color: tone ?? "var(--fg-primary)", textAlign: "right" }}>
        {value}
      </span>
    </div>
  );
}

/** Detail for whatever was clicked on the canvas.
 *
 * Everything here is derived from the subgraph the canvas already holds -- the
 * HAS_ATTRIBUTE edges give both "which attributes does this client carry" and
 * "which clients share this attribute" -- so clicking a node costs no request.
 */
export function NodeDetail({ nodeId, ring, elements }: Props) {
  const setSelectedNode = useSelection((s) => s.setSelectedNode);
  const setFocusedAttribute = useSelection((s) => s.setFocusedAttribute);
  const isClient = nodeId.startsWith("client:");

  const edges = elements.filter((e) => e.data.kind === "HAS_ATTRIBUTE");
  const nodes = elements.filter((e) => !e.data.source);
  const node = nodes.find((n) => n.data.id === nodeId);
  if (!node) return null;

  const header = (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        marginBottom: 8,
      }}
    >
      <span className="caps" style={{ marginBottom: 0 }}>
        {isClient ? "client" : String(node.data.kind)}
      </span>
      <button
        onClick={() => setSelectedNode(null)}
        style={{ fontSize: 11, color: "var(--fg-muted)" }}
        aria-label="Clear node selection"
      >
        clear ✕
      </button>
    </div>
  );

  if (isClient) {
    const member = ring.members.find((m) => m.id === nodeId);
    const held = edges
      .filter((e) => e.data.source === nodeId)
      .map((e) => nodes.find((n) => n.data.id === e.data.target))
      .filter(Boolean);

    return (
      <div
        style={{
          padding: 12,
          background: "var(--bg-raised)",
          borderBottom: "1px solid var(--border-subtle)",
        }}
      >
        {header}
        <div
          className="mono"
          style={{ fontSize: 14, marginBottom: 8, wordBreak: "break-all" }}
          title={member?.uid}
        >
          {member ? truncateId(member.uid, 10, 6) : nodeId}
        </div>
        {member && (
          <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
            <Row label="status" value={member.is_fraud ? "fraudulent" : "not flagged"}
                 tone={member.is_fraud ? "var(--risk-4)" : undefined} />
            <Row label="transactions" value={String(member.n_transactions)} />
            <Row label="total amount" value={formatAmount(member.total_amount)} />
            <Row label="active" value={`day ${member.first_day}–${member.last_day}`} />
            <Row label="shares" value={`${held.length} attributes`} />
          </div>
        )}
        {held.length > 0 && (
          <div style={{ marginTop: 8, display: "flex", flexWrap: "wrap", gap: 4 }}>
            {held.map((a) => (
              <button
                key={String(a!.data.id)}
                onClick={() => setFocusedAttribute(String(a!.data.id))}
                style={{
                  fontSize: 10,
                  padding: "2px 6px",
                  borderRadius: "var(--radius-chip)",
                  background: "var(--bg-sunken)",
                  border: "1px solid var(--border-default)",
                  color: "var(--fg-secondary)",
                }}
              >
                {String(a!.data.kind)} <span className="mono">{String(a!.data.label)}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Attribute node: who shares it, and how unusual that is.
  const sharers = edges
    .filter((e) => e.data.target === nodeId)
    .map((e) => ring.members.find((m) => m.id === e.data.source))
    .filter(Boolean);
  const fraudulent = sharers.filter((m) => m!.is_fraud).length;

  return (
    <div
      style={{
        padding: 12,
        background: "var(--bg-raised)",
        borderBottom: "1px solid var(--border-subtle)",
      }}
    >
      {header}
      <div className="mono" style={{ fontSize: 14, marginBottom: 8, wordBreak: "break-all" }}>
        {String(node.data.label)}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
        <Row label="shared by" value={`${sharers.length} of ${ring.n_clients} clients`} />
        <Row
          label="of those, fraudulent"
          value={String(fraudulent)}
          tone={fraudulent > 0 ? "var(--risk-4)" : undefined}
        />
      </div>
      <button
        onClick={() => setFocusedAttribute(nodeId)}
        style={{
          marginTop: 8,
          fontSize: 11,
          padding: "3px 8px",
          borderRadius: "var(--radius-control)",
          border: "1px solid var(--accent)",
          background: "var(--accent-muted)",
          color: "var(--accent)",
        }}
      >
        isolate on canvas
      </button>
      <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 2 }}>
        {sharers.map((m) => (
          <div
            key={m!.id}
            style={{ display: "flex", justifyContent: "space-between", fontSize: 10 }}
          >
            <span className="mono" style={{ color: "var(--fg-secondary)" }}>
              {truncateId(m!.uid)}
            </span>
            <span style={{ color: m!.is_fraud ? "var(--risk-4)" : "var(--fg-muted)" }}>
              {m!.is_fraud ? "fraud" : "—"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
