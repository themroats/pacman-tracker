/**
 * PlanDetail — display a coverage plan's routes with status and GPX export.
 */

import { plansApi } from "@/api/client";
import type { CoveragePlanResponse } from "@/types/api";

interface PlanDetailProps {
  plan: CoveragePlanResponse;
  /** Called when user clicks "View" on a route — parent shows it on the map. */
  onViewRoute?: (routeId: number) => void;
  /** Called when user clicks "Show All" — parent loads all route geometries. */
  onViewAllRoutes?: (routeIds: number[]) => void;
  /** The set of route IDs currently shown on the map. */
  viewingRouteIds?: Set<number>;
}

export default function PlanDetail({ plan, onViewRoute, onViewAllRoutes, viewingRouteIds }: PlanDetailProps) {

  const handleExportGpx = async (routeId: number) => {
    try {
      const file = await plansApi.fetchRouteGpx(routeId);
      const url = URL.createObjectURL(file);
      const a = document.createElement("a");
      a.href = url;
      a.download = file.name;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Failed to export GPX:", err);
    }
  };

  const statusColors: Record<string, string> = {
    generating: "#3b82f6",
    ready: "#8b5cf6",
    failed: "#dc2626",
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      {/* Plan header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h3 style={{ margin: 0, fontSize: "1rem", fontWeight: 600 }}>
            {plan.neighborhood_name}
          </h3>
          <p style={{ margin: "0.25rem 0 0", fontSize: "0.8125rem", color: "#6b7280" }}>
            {plan.total_routes} routes · {(plan.total_distance_m / 1000).toFixed(1)} km total
          </p>
        </div>
        <span
          style={{
            padding: "2px 8px",
            borderRadius: "4px",
            fontSize: "0.75rem",
            fontWeight: 600,
            background: statusColors[plan.status] ?? "#9ca3af",
            color: "#fff",
          }}
        >
          {plan.status}
        </span>
      </div>

      {/* Show All Routes button */}
      {onViewAllRoutes && plan.routes.length > 1 && (() => {
        const allRouteIds = plan.routes.map((r) => r.route_id);
        const allShown = allRouteIds.every((id) => viewingRouteIds?.has(id));
        return (
          <button
            onClick={() => onViewAllRoutes(allRouteIds)}
            style={{
              width: "100%",
              padding: "6px 10px",
              fontSize: "0.8125rem",
              fontWeight: 600,
              borderRadius: "6px",
              border: allShown ? "1px solid #6366f1" : "1px solid #d1d5db",
              background: allShown ? "#eef2ff" : "#f9fafb",
              color: allShown ? "#6366f1" : "#374151",
              cursor: "pointer",
            }}
          >
            {allShown ? "Hide All Routes" : "Show All Routes on Map"}
          </button>
        );
      })()}

      {plan.error_message && (
        <p style={{ color: "#dc2626", fontSize: "0.8rem", margin: 0 }}>{plan.error_message}</p>
      )}

      {/* Route list */}
      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        {plan.routes.map((route) => (
          <div
            key={route.sequence_order}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "0.5rem 0.75rem",
              background: "#fafafa",
              borderRadius: "6px",
              border: "1px solid #e5e7eb",
            }}
          >
            <div>
              <span style={{ fontWeight: 600, fontSize: "0.875rem" }}>Route {route.sequence_order}</span>
              <span style={{ fontSize: "0.8125rem", color: "#6b7280", marginLeft: "0.5rem" }}>
                {(route.distance_meters / 1000).toFixed(1)} km ·{" "}
                {Math.round(route.estimated_duration_seconds / 60)} min ·{" "}
                {route.streets_targeted} streets
              </span>
            </div>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              {onViewRoute && (
                <button
                  onClick={() => onViewRoute(route.route_id)}
                  style={{
                    padding: "4px 8px",
                    fontSize: "0.75rem",
                    borderRadius: "4px",
                    border: viewingRouteIds?.has(route.route_id) ? "1px solid #6366f1" : "1px solid #d1d5db",
                    background: viewingRouteIds?.has(route.route_id) ? "#eef2ff" : "#fff",
                    color: viewingRouteIds?.has(route.route_id) ? "#6366f1" : undefined,
                    cursor: "pointer",
                    fontWeight: viewingRouteIds?.has(route.route_id) ? 600 : undefined,
                  }}
                >
                  {viewingRouteIds?.has(route.route_id) ? "Viewing" : "View"}
                </button>
              )}
              <button
                onClick={() => handleExportGpx(route.route_id)}
                style={{
                  padding: "4px 8px",
                  fontSize: "0.75rem",
                  borderRadius: "4px",
                  border: "1px solid #d1d5db",
                  background: "#fff",
                  cursor: "pointer",
                }}
              >
                GPX
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
