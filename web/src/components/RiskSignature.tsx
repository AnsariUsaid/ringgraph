import { AXIS_ORDER, type AxisName } from "../api/types";
import { riskColor } from "../lib/risk";

interface Props {
  axes: Record<AxisName, number>;
  width?: number;
  height?: number;
  labels?: boolean;
}

/** Four bars in a fixed order: density, synchrony, concentration, tightness.
 *
 * Because the order never changes, the glyph becomes a readable *shape* -- a
 * ring flagged purely on synchrony looks visibly different at 20px from one
 * flagged on concentration, and after a little exposure it reads without the
 * legend. Rendered everywhere a ring appears, including the brand mark.
 */
export function RiskSignature({ axes, width = 44, height = 14, labels = false }: Props) {
  const gap = Math.max(2, width * 0.045);
  const barWidth = (width - gap * (AXIS_ORDER.length - 1)) / AXIS_ORDER.length;
  const radius = Math.min(2.5, barWidth / 3);

  return (
    <svg
      width={width}
      height={labels ? height + 14 : height}
      role="img"
      aria-label={AXIS_ORDER.map((a) => `${a} ${((axes[a] ?? 0) * 100).toFixed(0)}%`).join(", ")}
      style={{ display: "block", flexShrink: 0, overflow: "visible" }}
    >
      {AXIS_ORDER.map((axis, index) => {
        const value = axes[axis] ?? 0;
        const barHeight = Math.max(1.5, value * height);
        const x = index * (barWidth + gap);
        return (
          <g key={axis}>
            {/* The track is the unfilled remainder, which is what lets the
                glyph be read as a proportion rather than as four free bars. */}
            <rect x={x} y={0} width={barWidth} height={height} fill="var(--paper-sunken)" rx={radius} />
            <rect
              x={x}
              y={height - barHeight}
              width={barWidth}
              height={barHeight}
              fill={riskColor(value)}
              rx={radius}
              style={{ transition: "height 320ms var(--ease-out), y 320ms var(--ease-out)" }}
            />
            {labels && (
              <text
                x={x + barWidth / 2}
                y={height + 10}
                textAnchor="middle"
                fontSize={8.5}
                fontWeight={600}
                fill="var(--ink-3)"
                style={{ textTransform: "uppercase", letterSpacing: "0.08em" }}
              >
                {axis.slice(0, 3)}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}
