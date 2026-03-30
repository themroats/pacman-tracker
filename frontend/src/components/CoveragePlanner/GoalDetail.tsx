/**
 * GoalDetail — display a city-level coverage goal with its neighborhood plans.
 */

import type { CoverageGoalResponse } from "@/types/api";

interface GoalDetailProps {
  goal: CoverageGoalResponse;
  onViewPlan: (planId: number) => void;
}

export default function GoalDetail({ goal, onViewPlan }: GoalDetailProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      {/* Header */}
      <div>
        <h3 style={{ margin: 0, fontSize: "1rem", fontWeight: 600 }}>
          Reach {goal.target_coverage_pct}% Coverage
        </h3>
        <p style={{ margin: "0.25rem 0 0", fontSize: "0.8125rem", color: "#6b7280" }}>
          {goal.neighborhoods.length} neighborhoods · {goal.total_routes} routes ·{" "}
          {(goal.total_distance_m / 1000).toFixed(1)} km total
        </p>
      </div>

      {/* Status */}
      {goal.status === "completed" && (
        <div style={{ padding: "0.75rem", background: "#ecfdf5", borderRadius: "8px", border: "1px solid #6ee7b7" }}>
          <p style={{ fontWeight: 600, color: "#059669", margin: 0 }}>
            You've already reached {goal.current_coverage_pct.toFixed(1)}% coverage!
          </p>
        </div>
      )}

      {/* Neighborhood list */}
      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        {goal.neighborhoods.map((n) => (
          <div
            key={n.neighborhood_id}
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "0.75rem",
              background: "#fafafa",
              borderRadius: "6px",
              border: "1px solid #e5e7eb",
            }}
          >
            <div>
              <span style={{ fontWeight: 600, fontSize: "0.875rem" }}>{n.neighborhood_name}</span>
              <span style={{ fontSize: "0.8125rem", color: "#6b7280", marginLeft: "0.5rem" }}>
                {n.current_coverage_pct.toFixed(1)}% covered · {n.untraveled_streets} streets left ·{" "}
                {n.estimated_routes} routes
              </span>
            </div>
            {n.plan_id && (
              <button
                onClick={() => onViewPlan(n.plan_id!)}
                style={{
                  padding: "4px 12px",
                  fontSize: "0.75rem",
                  borderRadius: "4px",
                  border: "1px solid #c4b5fd",
                  background: "#faf5ff",
                  cursor: "pointer",
                  fontWeight: 500,
                }}
              >
                View plan →
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
