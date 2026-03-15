/**
 * T071 — StatsOverview
 *
 * Displays overall user statistics: total activities, distance, unique streets,
 * and per-city breakdown.
 */

import type { OverallStatsResponse } from "@/types/api";

interface StatsOverviewProps {
  stats: OverallStatsResponse;
}

function formatNumber(n: number): string {
  return n.toLocaleString("en-US");
}

export default function StatsOverview({ stats }: StatsOverviewProps) {
  return (
    <div>
      {/* Top-level stats */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: "1rem",
          marginBottom: "1.5rem",
        }}
      >
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "0.75rem", color: "#6b7280" }}>Activities</div>
          <div style={{ fontSize: "1.5rem", fontWeight: 700 }}>
            {formatNumber(stats.total_activities)}
          </div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "0.75rem", color: "#6b7280" }}>Distance</div>
          <div style={{ fontSize: "1.5rem", fontWeight: 700 }}>
            {formatNumber(Math.round(stats.total_distance_meters / 1000))} km
          </div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "0.75rem", color: "#6b7280" }}>Unique Streets</div>
          <div style={{ fontSize: "1.5rem", fontWeight: 700 }}>
            {formatNumber(stats.total_unique_streets)}
          </div>
        </div>
      </div>

      {/* Per-city table */}
      {stats.cities.length > 0 && (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
          <thead>
            <tr style={{ borderBottom: "2px solid #e5e7eb" }}>
              <th style={{ textAlign: "left", padding: "6px 8px" }}>City</th>
              <th style={{ textAlign: "right", padding: "6px 8px" }}>Coverage</th>
              <th style={{ textAlign: "right", padding: "6px 8px" }}>Traveled</th>
              <th style={{ textAlign: "right", padding: "6px 8px" }}>Total</th>
            </tr>
          </thead>
          <tbody>
            {stats.cities.map((c) => (
              <tr key={c.city_name} style={{ borderBottom: "1px solid #f3f4f6" }}>
                <td style={{ padding: "6px 8px" }}>{c.city_name}</td>
                <td style={{ padding: "6px 8px", textAlign: "right" }}>
                  {c.coverage_percentage.toFixed(1)}%
                </td>
                <td style={{ padding: "6px 8px", textAlign: "right" }}>
                  {formatNumber(c.streets_traveled)}
                </td>
                <td style={{ padding: "6px 8px", textAlign: "right" }}>
                  {formatNumber(c.streets_total)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
