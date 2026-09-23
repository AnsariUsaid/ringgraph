import type { TimelineResponse } from "../api/types";
import { truncateId } from "../lib/risk";

const LANE_HEIGHT = 15;
const LANE_GAP = 3;
const LEFT = 78;
const RIGHT = 10;
const TOP = 16;
const MAX_LANES = 22;

/** Event raster: one lane per client, events as ticks on a shared time axis.
 *
 * This form rather than a line chart or histogram because **vertical alignment
 * across lanes *is* synchrony**, and the visual system detects that with no
 * training. A line chart would imply continuity between discrete events; a
 * histogram would destroy per-member attribution, which is the whole question
 * (D-31). Lanes are sorted by first event, so a coordinated burst forms a
 * vertical wall and a sequential cascade forms a diagonal -- and the diagonal
 * is itself a finding.
 *
 * Hand-rolled SVG rather than a chart library: none has a raster primitive, and
 * per-point React elements are heavy at hundreds of marks.
 */
export function TemporalStrip({ data, width = 356 }: { data: TimelineResponse; width?: number }) {
  const lanes = data.lanes.slice(0, MAX_LANES);
  const hidden = data.lanes.length - lanes.length;
  const height = TOP + lanes.length * (LANE_HEIGHT + LANE_GAP) + 18;
  const plotWidth = width - LEFT - RIGHT;

  // A ring that fires in one instant would otherwise render as a single line
  // at x=0, so enforce a minimum visible span.
  const rawSpan = data.t_max - data.t_min;
  const span = Math.max(rawSpan, 3600);
  const x = (t: number) => LEFT + ((t - data.t_min) / span) * plotWidth;

  // Label the axis that is *drawn*, not the raw extent. A ring whose events
  // all land in the same second has rawSpan 0, and labelling five ticks
  // "0.0h" made a real finding -- a perfectly simultaneous burst -- look like
  // a rendering bug. The drawn window is at least an hour, so say so, and call
  // out the instantaneous case in words underneath.
  const hours = span / 3600;
  const instant = rawSpan < 60;
  const ticks = [0, 0.25, 0.5, 0.75, 1];

  return (
    <svg width={width} height={height} style={{ display: "block" }}>
      {ticks.map((fraction) => (
        <g key={fraction}>
          <line
            x1={LEFT + fraction * plotWidth}
            x2={LEFT + fraction * plotWidth}
            y1={TOP - 4}
            y2={height - 16}
            stroke="var(--rule)"
            strokeWidth={1}
          />
          <text
            x={LEFT + fraction * plotWidth}
            y={TOP - 7}
            fontSize={9}
            fill="var(--ink-3)"
            textAnchor="middle"
            className="mono"
          >
            {(fraction * hours).toFixed(hours < 6 ? 1 : 0)}h
          </text>
        </g>
      ))}

      {lanes.map((lane, index) => {
        const y = TOP + index * (LANE_HEIGHT + LANE_GAP);
        return (
          <g key={lane.id}>
            <text x={0} y={y + 11} fontSize={10} fill="var(--ink-3)" className="mono">
              {truncateId(lane.uid, 5, 3)}
            </text>
            <rect x={LEFT} y={y} width={plotWidth} height={LANE_HEIGHT} fill="var(--paper-sunken)" rx={3} />
            {lane.events.map((event, i) => (
              <rect
                key={i}
                // Ticks rather than circles: they pack better at density and
                // their vertical extent reinforces cross-lane alignment.
                x={Math.min(x(event.t), LEFT + plotWidth - 3)}
                y={y + 2}
                width={3}
                height={LANE_HEIGHT - 4}
                rx={1}
                fill={event.is_fraud ? "var(--risk-4)" : "var(--ink-4)"}
              >
                <title>
                  day {event.day} · ${event.amount.toFixed(2)}
                  {event.is_fraud ? " · fraud" : ""}
                </title>
              </rect>
            ))}
          </g>
        );
      })}

      {instant && (
        <text x={LEFT} y={height - 4} fontSize={10} fill="var(--risk-4)" fontWeight={600}>
          every event inside one second
        </text>
      )}

      {hidden > 0 && (
        <text x={0} y={height - 4} fontSize={10} fill="var(--ink-3)">
          +{hidden} more members
        </text>
      )}
    </svg>
  );
}
