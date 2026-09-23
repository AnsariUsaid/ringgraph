/** The brand mark: the risk-signature glyph, four bars in the fixed axis order.
 *
 * A logo that is a piece of the data language rather than a generic icon is
 * free identity -- the same shape appears on every ring row in the workbench,
 * so the mark teaches the glyph before the reader has seen a single ring.
 *
 * Kept in its own file because it is drawn in three places that must not drift:
 * the navbar, and `public/favicon.svg`, which is hand-written to match because
 * a favicon cannot import a React component.
 */
export function Mark({ size = 20 }: { size?: number }) {
  // Heights as fractions of the box, so the shape is identical at 20px and at
  // 64px. The last bar is the tall crimson one: a ring flagged on tightness.
  const bars = [0.41, 0.76, 0.53, 1];
  const width = size;
  const height = size * 0.9;
  const gap = width * 0.09;
  const barWidth = (width - gap * 3) / 4;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      aria-hidden
      style={{ display: "block", flexShrink: 0 }}
    >
      {bars.map((fraction, i) => (
        <rect
          key={i}
          x={i * (barWidth + gap)}
          y={height * (1 - fraction)}
          width={barWidth}
          height={height * fraction}
          rx={barWidth * 0.32}
          fill={i === 3 ? "var(--risk-4)" : "var(--accent)"}
          opacity={i === 3 ? 1 : 0.34 + i * 0.22}
        />
      ))}
    </svg>
  );
}
