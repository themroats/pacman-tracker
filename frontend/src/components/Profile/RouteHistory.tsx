/**
 * RouteHistory — lists route suggestions from GET /routes/history.
 */

import { useEffect, useState } from "react";
import { routesApi } from "@/api/client";
import { useIsMobile } from "@/hooks/useIsMobile";
import type { RouteHistoryItem } from "@/types/api";

function formatDistance(meters: number): string {
  return `${(meters / 1000).toFixed(1)} km`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function RouteHistory() {
  const isMobile = useIsMobile();
  const [routes, setRoutes] = useState<RouteHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    routesApi
      .history()
      .then((data) => setRoutes(data.routes))
      .finally(() => setLoading(false));
  }, []);

  const handleExportGpx = async (routeId: number) => {
    const file = await routesApi.fetchGpx(routeId);
    const url = URL.createObjectURL(file);
    const a = document.createElement("a");
    a.href = url;
    a.download = file.name;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (loading) return <p style={{ color: "#6b7280" }}>Loading route history...</p>;
  if (routes.length === 0) return <p style={{ color: "#6b7280" }}>No route suggestions yet.</p>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
      {routes.map((r) => (
        <div
          key={r.id}
          style={{
            display: "flex",
            alignItems: isMobile ? "flex-start" : "center",
            flexDirection: isMobile ? "column" : "row",
            gap: isMobile ? "0.25rem" : "1rem",
            padding: "0.75rem",
            borderRadius: "8px",
            border: "1px solid #e5e7eb",
            backgroundColor: "#fff",
            fontSize: "0.875rem",
          }}
        >
          <div style={{ flex: 1 }}>
            <span style={{ fontWeight: 600 }}>
              {r.neighborhood_name || r.city_name}
            </span>
            <span style={{ marginLeft: "0.5rem", fontSize: "0.8125rem", color: "#6b7280" }}>
              {formatDate(r.created_at)}
            </span>
          </div>
          <div style={{ display: "flex", gap: "1rem", fontSize: "0.8125rem", color: "#374151", alignItems: "center" }}>
            <span>{formatDistance(r.distance_meters)}</span>
            <span style={{ color: "#3b82f6" }}>
              {(r.untraveled_ratio * 100).toFixed(0)}% new
            </span>
            <button
              onClick={() => handleExportGpx(r.id)}
              style={{
                fontSize: "0.75rem",
                padding: "2px 8px",
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
  );
}
