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
 * legend (D-30). Rendered everywhere a ring appears.
 */
export function RiskSignature({ axes, width = 44, height = 14, labels = false }: Props) {
  const gap = 2;
  const barWidth = (width - gap * (AXIS_ORDER.length - 1)) / AXIS_ORDER.length;

  return (
    <svg
      width={width}
      height={labels ? height + 12 : height}
      role="img"
      aria-label={AXIS_ORDER.map((a) => `${a} ${(axes[a] * 100).toFixed(0)}%`).join(", ")}
      style={{ display: "block", flexShrink: 0 }}
    >
      {AXIS_ORDER.map((axis, index) => {
        const value = axes[axis] ?? 0;
        const barHeight = Math.max(1.5, value * height);
        return (
          <g key={axis}>
            <rect
              x={index * (barWidth + gap)}
              y={0}
              width={barWidth}
              height={height}
              fill="var(--bg-sunken)"
              rx={1}
            />
            <rect
              x={index * (barWidth + gap)}
              y={height - barHeight}
              width={barWidth}
              height={barHeight}
              fill={riskColor(value)}
              rx={1}
            />
            {labels && (
              <text
                x={index * (barWidth + gap) + barWidth / 2}
                y={height + 9}
                textAnchor="middle"
                fontSize={8}
                fill="var(--fg-muted)"
                style={{ textTransform: "uppercase", letterSpacing: "0.04em" }}
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
