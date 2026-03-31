/**
 * PlanHistory — lists coverage plans with inline detail expansion and route preview map.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { MapContainer, TileLayer, GeoJSON } from "react-leaflet";
import { plansApi, routesApi } from "@/api/client";
import { useIsMobile } from "@/hooks/useIsMobile";
import type { CoveragePlanSummary, CoveragePlanResponse } from "@/types/api";
import type { LatLngBoundsExpression } from "leaflet";
import "leaflet/dist/leaflet.css";

const TILE_URL = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";

const ROUTE_COLORS = [
  "#6366f1", "#3b82f6", "#06b6d4", "#10b981", "#f59e0b",
  "#ef4444", "#ec4899", "#8b5cf6", "#14b8a6", "#f97316",
];

function formatDistance(meters: number): string {
  return `${(meters / 1000).toFixed(1)} km`;
}

function statusColor(status: string): string {
  switch (status) {
    case "ready":
      return "#22c55e";
    case "generating":
      return "#f59e0b";
    case "in_progress":
      return "#3b82f6";
    case "failed":
      return "#ef4444";
    case "completed":
      return "#22c55e";
    default:
      return "#6b7280";
  }
}

function getBoundsFromFeatures(features: GeoJSON.Feature[]): LatLngBoundsExpression | null {
  let minLat = Infinity, maxLat = -Infinity, minLng = Infinity, maxLng = -Infinity;
  let hasCoords = false;

  const processCoords = (coords: number[][]) => {
    for (const coord of coords) {
      const lng = coord[0];
      const lat = coord[1];
      if (lng === undefined || lat === undefined) continue;
      hasCoords = true;
      if (lat < minLat) minLat = lat;
      if (lat > maxLat) maxLat = lat;
      if (lng < minLng) minLng = lng;
      if (lng > maxLng) maxLng = lng;
    }
  };

  for (const f of features) {
    const geom = f.geometry;
    if (geom.type === "LineString") {
      processCoords(geom.coordinates as number[][]);
    } else if (geom.type === "MultiLineString") {
      for (const line of (geom.coordinates as number[][][])) {
        processCoords(line);
      }
    }
  }
  if (!hasCoords) return null;
  return [
    [minLat - 0.002, minLng - 0.002],
    [maxLat + 0.002, maxLng + 0.002],
  ];
}

export default function PlanHistory() {
  const isMobile = useIsMobile();
  const [plans, setPlans] = useState<CoveragePlanSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [routePage, setRoutePage] = useState(0);
  const detailCache = useRef<Map<number, CoveragePlanResponse>>(new Map());
  const [detail, setDetail] = useState<CoveragePlanResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Route preview map state
  const routeGeoCache = useRef<Map<number, GeoJSON.Feature>>(new Map());
  const [visibleRoutes, setVisibleRoutes] = useState<Map<number, GeoJSON.Feature>>(new Map());
  const [routeLoading, setRouteLoading] = useState<Set<number>>(new Set());

  useEffect(() => {
    plansApi
      .list()
      .then((all) => setPlans(all.filter((p) => p.goal_id === null)))
      .finally(() => setLoading(false));
  }, []);

  const handleToggle = (planId: number) => {
    if (expandedId === planId) {
      setExpandedId(null);
      setVisibleRoutes(new Map());
      return;
    }
    setExpandedId(planId);
    setRoutePage(0);
    const cached = detailCache.current.get(planId);
    if (cached) {
      setDetail(cached);
      return;
    }
    setDetail(null);
    setDetailLoading(true);
    plansApi
      .get(planId)
      .then((d) => {
        detailCache.current.set(planId, d);
        setDetail(d);
      })
      .finally(() => setDetailLoading(false));
  };

  const handleExportGpx = async (routeId: number) => {
    const file = await routesApi.fetchGpx(routeId);
    const url = URL.createObjectURL(file);
    const a = document.createElement("a");
    a.href = url;
    a.download = file.name;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDelete = async (planId: number, name: string) => {
    if (!window.confirm(`Delete plan for "${name}"? This cannot be undone.`)) return;
    await plansApi.remove(planId);
    setPlans((prev) => prev.filter((p) => p.id !== planId));
    detailCache.current.delete(planId);
    if (expandedId === planId) {
      setExpandedId(null);
      setDetail(null);
      setVisibleRoutes(new Map());
    }
  };

  const handleViewRoute = useCallback(async (routeId: number) => {
    // Toggle off
    if (visibleRoutes.has(routeId)) {
      setVisibleRoutes((prev) => { const next = new Map(prev); next.delete(routeId); return next; });
      return;
    }
    // Check cache
    const cached = routeGeoCache.current.get(routeId);
    if (cached) {
      setVisibleRoutes((prev) => new Map(prev).set(routeId, cached));
      return;
    }
    // Fetch
    setRouteLoading((prev) => new Set(prev).add(routeId));
    try {
      const feature = await routesApi.geojson(routeId);
      routeGeoCache.current.set(routeId, feature);
      setVisibleRoutes((prev) => new Map(prev).set(routeId, feature));
    } catch (err) {
      console.error("Failed to load route geometry:", err);
    } finally {
      setRouteLoading((prev) => { const next = new Set(prev); next.delete(routeId); return next; });
    }
  }, [visibleRoutes]);

  const handleShowAll = useCallback(async () => {
    if (!detail) return;
    const routeIds = detail.routes.map((r) => r.route_id);
    // If all shown, toggle all off
    if (routeIds.every((id) => visibleRoutes.has(id))) {
      setVisibleRoutes(new Map());
      return;
    }
    // Load missing
    const toLoad = routeIds.filter((id) => !routeGeoCache.current.has(id));
    if (toLoad.length > 0) {
      setRouteLoading(new Set(toLoad));
      try {
        const results = await Promise.all(
          toLoad.map((id) => routesApi.geojson(id).then((f) => [id, f] as const))
        );
        for (const [id, f] of results) routeGeoCache.current.set(id, f);
      } catch (err) {
        console.error("Failed to load route geometries:", err);
      } finally {
        setRouteLoading(new Set());
      }
    }
    const all = new Map<number, GeoJSON.Feature>();
    for (const id of routeIds) {
      const f = routeGeoCache.current.get(id);
      if (f) all.set(id, f);
    }
    setVisibleRoutes(all);
  }, [detail, visibleRoutes]);

  const ROUTE_PAGE_SIZE = 10;

  if (loading) return <p style={{ color: "#6b7280" }}>Loading plans...</p>;
  if (plans.length === 0) return <p style={{ color: "#6b7280" }}>No coverage plans yet.</p>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
      {plans.map((plan) => (
        <div key={plan.id} style={{ position: "relative" }}>
          <button
            onClick={() => handleToggle(plan.id)}
            style={{
              display: "flex",
              alignItems: isMobile ? "flex-start" : "center",
              flexDirection: isMobile ? "column" : "row",
              gap: isMobile ? "0.25rem" : "1rem",
              width: "100%",
              padding: "0.75rem",
              paddingRight: "2rem",
              borderRadius: expandedId === plan.id ? "8px 8px 0 0" : "8px",
              border: "1px solid #e5e7eb",
              borderBottom: expandedId === plan.id ? "none" : "1px solid #e5e7eb",
              textAlign: "left",
              cursor: "pointer",
              backgroundColor: expandedId === plan.id ? "#f9fafb" : "#fff",
              fontSize: "0.875rem",
            }}
          >
            <div style={{ flex: 1 }}>
              <span style={{ fontWeight: 600 }}>{plan.neighborhood_name}</span>
              <span
                style={{
                  marginLeft: "0.5rem",
                  fontSize: "0.75rem",
                  color: statusColor(plan.status),
                  fontWeight: 500,
                }}
              >
                {plan.status}
              </span>
            </div>
            <div style={{ display: "flex", gap: "1rem", fontSize: "0.8125rem", color: "#6b7280", alignItems: "center" }}>
              <span>{plan.total_routes} routes</span>
              <span>{formatDistance(plan.total_distance_m)}</span>
              <span>{plan.initial_coverage_pct.toFixed(0)}% start</span>
            </div>
          </button>
          <span
            role="button"
            tabIndex={0}
            onClick={(e) => {
              e.stopPropagation();
              handleDelete(plan.id, plan.neighborhood_name);
            }}
            onKeyDown={(e) => { if (e.key === "Enter") handleDelete(plan.id, plan.neighborhood_name); }}
            title="Delete plan"
            style={{
              position: "absolute",
              top: "50%",
              right: "0.5rem",
              transform: "translateY(-50%)",
              cursor: "pointer",
              color: "#d1d5db",
              fontSize: "0.875rem",
              padding: "4px 6px",
              lineHeight: 1,
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "#ef4444")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "#d1d5db")}
          >
            ✕
          </span>

          {/* Inline detail */}
          {expandedId === plan.id && (
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
                <p style={{ color: "#6b7280", fontSize: "0.8125rem" }}>Loading routes...</p>
              ) : detail ? (
                <div>
                  <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginBottom: "0.75rem", flexWrap: "wrap" }}>
                    <div style={{ fontSize: "0.8125rem", color: "#6b7280", flex: 1 }}>
                      Target: {detail.target_coverage_pct.toFixed(0)}% &middot;{" "}
                      Total: {formatDistance(detail.total_distance_m)}
                      {detail.error_message && (
                        <span style={{ color: "#ef4444" }}> &middot; {detail.error_message}</span>
                      )}
                    </div>
                    {detail.routes.length > 0 && (
                      <button
                        onClick={handleShowAll}
                        style={{
                          fontSize: "0.75rem",
                          padding: "3px 10px",
                          borderRadius: "4px",
                          border: "1px solid #d1d5db",
                          background: detail.routes.every((r) => visibleRoutes.has(r.route_id)) ? "#eef2ff" : "#fff",
                          cursor: "pointer",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {detail.routes.every((r) => visibleRoutes.has(r.route_id)) ? "Hide All" : "Show All"}
                      </button>
                    )}
                  </div>

                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8125rem" }}>
                    <thead>
                      <tr style={{ borderBottom: "1px solid #e5e7eb" }}>
                        <th style={{ textAlign: "left", padding: "4px 6px" }}>#</th>
                        <th style={{ textAlign: "right", padding: "4px 6px" }}>Distance</th>
                        <th style={{ textAlign: "right", padding: "4px 6px" }}>Streets</th>
                        <th style={{ textAlign: "right", padding: "4px 6px" }}>Match %</th>
                        <th style={{ textAlign: "right", padding: "4px 6px" }}></th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.routes.slice(routePage * ROUTE_PAGE_SIZE, (routePage + 1) * ROUTE_PAGE_SIZE).map((r, idx) => {
                        const globalIdx = routePage * ROUTE_PAGE_SIZE + idx;
                        return (
                        <tr key={r.route_id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                          <td style={{ padding: "4px 6px" }}>
                            {visibleRoutes.has(r.route_id) && (
                              <span style={{
                                display: "inline-block",
                                width: 8,
                                height: 8,
                                borderRadius: "50%",
                                backgroundColor: ROUTE_COLORS[globalIdx % ROUTE_COLORS.length],
                                marginRight: 4,
                              }} />
                            )}
                            {r.sequence_order}
                          </td>
                          <td style={{ padding: "4px 6px", textAlign: "right" }}>
                            {formatDistance(r.distance_meters)}
                          </td>
                          <td style={{ padding: "4px 6px", textAlign: "right" }}>
                            {r.streets_targeted}
                          </td>
                          <td style={{ padding: "4px 6px", textAlign: "right" }}>
                            {(r.untraveled_ratio * 100).toFixed(0)}%
                          </td>
                          <td style={{ padding: "4px 6px", textAlign: "right", whiteSpace: "nowrap" }}>
                            <button
                              onClick={() => handleViewRoute(r.route_id)}
                              disabled={routeLoading.has(r.route_id)}
                              style={{
                                fontSize: "0.75rem",
                                padding: "2px 8px",
                                borderRadius: "4px",
                                border: "1px solid #d1d5db",
                                background: visibleRoutes.has(r.route_id) ? "#eef2ff" : "#fff",
                                cursor: "pointer",
                                marginRight: 4,
                              }}
                            >
                              {routeLoading.has(r.route_id) ? "..." : visibleRoutes.has(r.route_id) ? "Hide" : "View"}
                            </button>
                            <button
                              onClick={() => handleExportGpx(r.route_id)}
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
                          </td>
                        </tr>
                        );
                      })}
                    </tbody>
                  </table>

                  {/* Route pagination */}
                  {detail.routes.length > ROUTE_PAGE_SIZE && (() => {
                    const routeTotalPages = Math.ceil(detail.routes.length / ROUTE_PAGE_SIZE);
                    return (
                      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: "0.75rem", marginTop: "0.5rem", fontSize: "0.8125rem" }}>
                        <button
                          disabled={routePage === 0}
                          onClick={() => setRoutePage((p) => p - 1)}
                          style={{ padding: "3px 10px", borderRadius: "4px", border: "1px solid #d1d5db", background: "#fff", cursor: routePage === 0 ? "default" : "pointer", opacity: routePage === 0 ? 0.4 : 1 }}
                        >
                          ← Prev
                        </button>
                        <span style={{ color: "#6b7280" }}>
                          {routePage * ROUTE_PAGE_SIZE + 1}–{Math.min((routePage + 1) * ROUTE_PAGE_SIZE, detail.routes.length)} of {detail.routes.length}
                        </span>
                        <button
                          disabled={routePage >= routeTotalPages - 1}
                          onClick={() => setRoutePage((p) => p + 1)}
                          style={{ padding: "3px 10px", borderRadius: "4px", border: "1px solid #d1d5db", background: "#fff", cursor: routePage >= routeTotalPages - 1 ? "default" : "pointer", opacity: routePage >= routeTotalPages - 1 ? 0.4 : 1 }}
                        >
                          Next →
                        </button>
                      </div>
                    );
                  })()}

                  {/* Inline route preview map */}
                  {visibleRoutes.size > 0 && (() => {
                    const routeFeatures = Array.from(visibleRoutes.values());
                    const allFeatures = routeFeatures as GeoJSON.Feature[];
                    const bounds = getBoundsFromFeatures(allFeatures);
                    if (!bounds) return null;
                    const routeIdToIdx = new Map(detail.routes.map((r, i) => [r.route_id, i]));
                    return (
                      <div style={{ marginTop: "0.75rem", borderRadius: "8px", overflow: "hidden", border: "1px solid #e5e7eb" }}>
                        <MapContainer
                          bounds={bounds}
                          style={{ height: isMobile ? "200px" : "280px", width: "100%" }}
                          scrollWheelZoom={false}
                        >
                          <TileLayer url={TILE_URL} attribution='&copy; <a href="https://carto.com/">CARTO</a>' />
                          {Array.from(visibleRoutes.entries()).map(([routeId, feature]) => (
                            <GeoJSON
                              key={routeId}
                              data={feature}
                              style={{
                                color: ROUTE_COLORS[(routeIdToIdx.get(routeId) ?? 0) % ROUTE_COLORS.length],
                                weight: 3,
                                opacity: 0.85,
                              }}
                            />
                          ))}
                        </MapContainer>
                      </div>
                    );
                  })()}
                </div>
              ) : null}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
