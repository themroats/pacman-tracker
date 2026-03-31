/**
 * GoalHistory — lists coverage goals with inline detail expansion.
 */

import { useEffect, useRef, useState } from "react";
import { goalsApi } from "@/api/client";
import { useIsMobile } from "@/hooks/useIsMobile";
import type { CoverageGoalSummary, CoverageGoalResponse } from "@/types/api";

function statusColor(status: string): string {
  switch (status) {
    case "ready":
      return "#22c55e";
    case "analyzing":
      return "#f59e0b";
    case "in_progress":
      return "#3b82f6";
    case "completed":
      return "#22c55e";
    default:
      return "#6b7280";
  }
}

export default function GoalHistory() {
  const isMobile = useIsMobile();
  const [goals, setGoals] = useState<CoverageGoalSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const detailCache = useRef<Map<number, CoverageGoalResponse>>(new Map());
  const [detail, setDetail] = useState<CoverageGoalResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    goalsApi
      .list()
      .then(setGoals)
      .finally(() => setLoading(false));
  }, []);

  const handleToggle = (goalId: number) => {
    if (expandedId === goalId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(goalId);
    const cached = detailCache.current.get(goalId);
    if (cached) {
      setDetail(cached);
      return;
    }
    setDetail(null);
    setDetailLoading(true);
    goalsApi
      .get(goalId)
      .then((d) => {
        detailCache.current.set(goalId, d);
        setDetail(d);
      })
      .finally(() => setDetailLoading(false));
  };

  if (loading) return <p style={{ color: "#6b7280" }}>Loading goals...</p>;
  if (goals.length === 0) return <p style={{ color: "#6b7280" }}>No coverage goals yet.</p>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
      {goals.map((goal) => (
        <div key={goal.id}>
          <button
            onClick={() => handleToggle(goal.id)}
            style={{
              display: "flex",
              alignItems: isMobile ? "flex-start" : "center",
              flexDirection: isMobile ? "column" : "row",
              gap: isMobile ? "0.25rem" : "1rem",
              width: "100%",
              padding: "0.75rem",
              borderRadius: expandedId === goal.id ? "8px 8px 0 0" : "8px",
              border: "1px solid #e5e7eb",
              borderBottom: expandedId === goal.id ? "none" : "1px solid #e5e7eb",
              textAlign: "left",
              cursor: "pointer",
              backgroundColor: expandedId === goal.id ? "#f9fafb" : "#fff",
              fontSize: "0.875rem",
            }}
          >
            <div style={{ flex: 1 }}>
              <span style={{ fontWeight: 600 }}>
                Goal: {goal.target_coverage_pct.toFixed(0)}% coverage
              </span>
              <span
                style={{
                  marginLeft: "0.5rem",
                  fontSize: "0.75rem",
                  color: statusColor(goal.status),
                  fontWeight: 500,
                }}
              >
                {goal.status}
              </span>
            </div>
            <div style={{ display: "flex", gap: "1rem", fontSize: "0.8125rem", color: "#6b7280" }}>
              <span>Currently {goal.current_coverage_pct.toFixed(1)}%</span>
              <span>{goal.total_neighborhoods} neighborhoods</span>
              <span>{goal.total_routes} routes</span>
            </div>
          </button>

          {/* Inline detail */}
          {expandedId === goal.id && (
            <div
              style={{
                border: "1px solid #e5e7eb",
                borderTop: "1px solid #f3f4f6",
                borderRadius: "0 0 8px 8px",
                padding: "0.75rem",
                backgroundColor: "#fafafa",
              }}
            >
              {detailLoading ? (
                <p style={{ color: "#6b7280", fontSize: "0.8125rem" }}>Loading details...</p>
              ) : detail ? (
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8125rem" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid #e5e7eb" }}>
                      <th style={{ textAlign: "left", padding: "4px 6px" }}>Neighborhood</th>
                      <th style={{ textAlign: "right", padding: "4px 6px" }}>Coverage</th>
                      <th style={{ textAlign: "right", padding: "4px 6px" }}>Untraveled</th>
                      <th style={{ textAlign: "right", padding: "4px 6px" }}>Est. Routes</th>
                      <th style={{ textAlign: "right", padding: "4px 6px" }}>Plan</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.neighborhoods.map((n) => (
                      <tr key={n.neighborhood_id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                        <td style={{ padding: "4px 6px" }}>{n.neighborhood_name}</td>
                        <td style={{ padding: "4px 6px", textAlign: "right" }}>
                          {n.current_coverage_pct.toFixed(1)}%
                        </td>
                        <td style={{ padding: "4px 6px", textAlign: "right" }}>
                          {n.untraveled_streets} streets
                        </td>
                        <td style={{ padding: "4px 6px", textAlign: "right" }}>
                          {n.estimated_routes}
                        </td>
                        <td style={{ padding: "4px 6px", textAlign: "right", fontSize: "0.75rem" }}>
                          {n.plan_status ? (
                            <span style={{ color: statusColor(n.plan_status) }}>{n.plan_status}</span>
                          ) : (
                            <span style={{ color: "#9ca3af" }}>—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : null}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
