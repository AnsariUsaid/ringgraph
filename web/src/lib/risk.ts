/** Map a 0..1 score onto the risk ramp. Low risk recedes, high risk advances. */
export function riskColor(value: number): string {
  if (value >= 0.9) return "var(--risk-4)";
  if (value >= 0.75) return "var(--risk-3)";
  if (value >= 0.5) return "var(--risk-2)";
  if (value >= 0.25) return "var(--risk-1)";
  return "var(--risk-0)";
}

/** Hashes are middle-truncated: reconstructed uids differ at the end, so
 *  cutting the tail makes distinct clients look identical. */
export function truncateId(id: string, head = 6, tail = 4): string {
  const bare = id.includes(":") ? id.slice(id.indexOf(":") + 1) : id;
  if (bare.length <= head + tail + 1) return bare;
  return `${bare.slice(0, head)}…${bare.slice(-tail)}`;
}

export function formatAmount(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}k`;
  return `$${value.toFixed(0)}`;
}

export const NODE_COLORS: Record<string, string> = {
  Client: "var(--node-client)",
  DeviceInfo: "var(--node-device)",
  id_33: "var(--node-screen)",
  id_30: "var(--node-os)",
  id_31: "var(--node-browser)",
};

export function nodeColor(kind: string): string {
  return NODE_COLORS[kind] ?? "var(--node-other)";
}
