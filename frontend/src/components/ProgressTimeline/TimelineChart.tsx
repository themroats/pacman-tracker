/**
 * TimelineChart
 *
 * Simple SVG line chart showing coverage percentage over time with milestone markers.
 * No external chart library — lightweight inline SVG approach.
 */

import type { TimelineEntry } from "@/types/api";
import { useIsMobile } from "@/hooks/useIsMobile";

interface TimelineChartProps {
  timeline: TimelineEntry[];
}

const CHART_WIDTH = 600;
const CHART_HEIGHT = 200;
const PADDING = { top: 20, right: 20, bottom: 40, left: 50 };

export default function TimelineChart({ timeline }: TimelineChartProps) {
  const isMobile = useIsMobile();
  if (timeline.length === 0) {
    return (
      <div style={{ padding: "2rem", textAlign: "center", color: "#9ca3af" }}>
        No data yet. Coverage snapshots will appear after syncing activities.
      </div>
    );
  }

  const innerW = CHART_WIDTH - PADDING.left - PADDING.right;
  const innerH = CHART_HEIGHT - PADDING.top - PADDING.bottom;

  const maxPct = Math.max(10, ...timeline.map((t) => t.coverage_percentage));
  const yScale = (pct: number) => PADDING.top + innerH - (pct / maxPct) * innerH;
  const xScale = (i: number) =>
    PADDING.left + (timeline.length === 1 ? innerW / 2 : (i / (timeline.length - 1)) * innerW);

  const points = timeline.map((t, i) => `${xScale(i)},${yScale(t.coverage_percentage)}`);
  const polyline = points.join(" ");

  // Y-axis ticks
  const yTicks = [0, 25, 50, 75, 100].filter((v) => v <= maxPct + 5);

  return (
    <div style={{ overflowX: "auto" }}>
      <svg
        viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
        style={{ width: "100%", maxWidth: isMobile ? undefined : CHART_WIDTH }}
      >
        {/* Grid lines */}
        {yTicks.map((tick) => (
          <g key={tick}>
            <line
              x1={PADDING.left}
              y1={yScale(tick)}
              x2={CHART_WIDTH - PADDING.right}
              y2={yScale(tick)}
              stroke="#e5e7eb"
              strokeDasharray="3,3"
            />
            <text
              x={PADDING.left - 8}
              y={yScale(tick) + 4}
              textAnchor="end"
              fontSize="10"
              fill="#6b7280"
            >
              {tick}%
            </text>
          </g>
        ))}

        {/* Line */}
        <polyline fill="none" stroke="#3b82f6" strokeWidth="2" points={polyline} />

        {/* Data points + labels */}
        {timeline.map((t, i) => (
          <g key={i}>
            <circle cx={xScale(i)} cy={yScale(t.coverage_percentage)} r="4" fill="#3b82f6" />
            <text
              x={xScale(i)}
              y={CHART_HEIGHT - 8}
              textAnchor="middle"
              fontSize="9"
              fill="#6b7280"
            >
              {t.date}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
