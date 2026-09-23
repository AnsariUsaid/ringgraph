/** Map a 0..1 score onto the risk ramp. Low risk recedes, high risk advances. */
export function riskColor(value: number): string {
  if (value >= 0.9) return "var(--risk-4)";
  if (value >= 0.75) return "var(--risk-3)";
  if (value >= 0.5) return "var(--risk-2)";
  if (value >= 0.25) return "var(--risk-1)";
  return "var(--risk-0)";
}

/** Middle-truncated so both ends stay visible.
 *
 *  Not because uids differ at the end -- they are blake2b digests, uniform at
 *  every position -- but because showing head and tail makes two ids easier to
 *  tell apart at a glance than a head-only prefix does. */
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
