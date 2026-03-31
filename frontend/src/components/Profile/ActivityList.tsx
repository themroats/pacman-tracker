/**
 * ActivityList — paginated activity list for the Profile page.
 *
 * Each row links to /profile/activity/:id for full detail.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { MapContainer, TileLayer, GeoJSON } from "react-leaflet";
import { activitiesApi } from "@/api/client";
import { useIsMobile } from "@/hooks/useIsMobile";
import type { ActivitySummary, ActivityListResponse } from "@/types/api";
import type { LatLngBoundsExpression } from "leaflet";
import "leaflet/dist/leaflet.css";

const PAGE_SIZE = 20;
const TILE_URL = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";

function getBoundsFromGeoJSON(fc: GeoJSON.FeatureCollection): LatLngBoundsExpression | null {
  if (!fc || !Array.isArray(fc.features)) return null;
  let minLat = Infinity, maxLat = -Infinity, minLng = Infinity, maxLng = -Infinity;
  let hasCoords = false;

  const processCoords = (coords: number[][]) => {
    for (const c of coords) {
      const lng = c[0], lat = c[1];
      if (lng === undefined || lat === undefined) continue;
      hasCoords = true;
      if (lat < minLat) minLat = lat;
      if (lat > maxLat) maxLat = lat;
      if (lng < minLng) minLng = lng;
      if (lng > maxLng) maxLng = lng;
    }
  };

  for (const f of fc.features) {
    const geom = f.geometry;
    if (geom.type === "LineString") processCoords(geom.coordinates as number[][]);
    else if (geom.type === "MultiLineString") {
      for (const line of geom.coordinates as number[][][]) processCoords(line);
    }
  }
  if (!hasCoords) return null;
  return [[minLat - 0.002, minLng - 0.002], [maxLat + 0.002, maxLng + 0.002]];
}

function formatDistance(meters: number): string {
  if (meters >= 1000) return `${(meters / 1000).toFixed(2)} km`;
  return `${Math.round(meters)} m`;
}

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function ActivityList() {
  const isMobile = useIsMobile();
  const [data, setData] = useState<ActivityListResponse | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  // Mini-map state
  const geoCache = useRef<Map<number, GeoJSON.FeatureCollection>>(new Map());
  const [visibleMapId, setVisibleMapId] = useState<number | null>(null);
  const [mapData, setMapData] = useState<GeoJSON.FeatureCollection | null>(null);
  const [mapLoading, setMapLoading] = useState(false);

  const handleToggleMap = useCallback(async (id: number, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (visibleMapId === id) {
      setVisibleMapId(null);
      setMapData(null);
      return;
    }
    const cached = geoCache.current.get(id);
    if (cached) {
      setVisibleMapId(id);
      setMapData(cached);
      return;
    }
    setVisibleMapId(id);
    setMapData(null);
    setMapLoading(true);
    try {
      const raw = await activitiesApi.getGeoJSON(id);
      // API returns a single Feature; wrap in FeatureCollection if needed
      const fc: GeoJSON.FeatureCollection = raw.type === "FeatureCollection"
        ? raw
        : { type: "FeatureCollection", features: [raw as unknown as GeoJSON.Feature] };
      geoCache.current.set(id, fc);
      setMapData(fc);
    } catch (err) {
      console.error("Failed to load activity GeoJSON:", err);
      setVisibleMapId(null);
    } finally {
      setMapLoading(false);
    }
  }, [visibleMapId]);

  useEffect(() => {
    setVisibleMapId(null);
    setMapData(null);
    setLoading(true);
    activitiesApi
      .list({ page, per_page: PAGE_SIZE })
      .then(setData)
      .finally(() => setLoading(false));
  }, [page]);

  if (loading && !data) {
    return <p style={{ color: "#6b7280" }}>Loading activities...</p>;
  }

  if (!data || data.activities.length === 0) {
    return <p style={{ color: "#6b7280" }}>No activities imported yet.</p>;
  }

  const totalPages = Math.ceil(data.total / PAGE_SIZE);

  return (
    <div>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        {data.activities.map((a: ActivitySummary) => (
          <div key={a.id}>
            <Link
              to={`/profile/activity/${a.id}`}
              style={{
                display: "flex",
                alignItems: isMobile ? "flex-start" : "center",
                flexDirection: isMobile ? "column" : "row",
                gap: isMobile ? "0.25rem" : "1rem",
                padding: "0.75rem",
                borderRadius: visibleMapId === a.id ? "8px 8px 0 0" : "8px",
                border: "1px solid #e5e7eb",
                borderBottom: visibleMapId === a.id ? "none" : "1px solid #e5e7eb",
                textDecoration: "none",
                color: "inherit",
                backgroundColor: "#fff",
                transition: "background-color 0.15s",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = "#f9fafb")}
              onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "#fff")}
            >
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontWeight: 600,
                    fontSize: "0.9375rem",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {a.name}
                </div>
                <div style={{ fontSize: "0.8125rem", color: "#6b7280" }}>
                  {a.sport_type} &middot; {formatDate(a.start_date)}
                  {a.city_name ? ` · ${a.city_name}` : ""}
                </div>
              </div>
              <div
                style={{
                  display: "flex",
                  gap: "1rem",
                  fontSize: "0.8125rem",
                  color: "#374151",
                  flexShrink: 0,
                  alignItems: "center",
                }}
              >
                <span>{formatDistance(a.distance_meters)}</span>
                <span>{formatDuration(a.duration_seconds)}</span>
                {a.has_gps && (
                  <button
                    onClick={(e) => handleToggleMap(a.id, e)}
                    style={{
                      fontSize: "0.75rem",
                      padding: "2px 8px",
                      borderRadius: "4px",
                      border: "1px solid #d1d5db",
                      background: visibleMapId === a.id ? "#eef2ff" : "#fff",
                      cursor: "pointer",
                      color: "#3b82f6",
                      fontWeight: 500,
                    }}
                  >
                    {mapLoading && visibleMapId === a.id ? "..." : visibleMapId === a.id ? "Hide" : "Map"}
                  </button>
                )}
              </div>
            </Link>

            {/* Inline mini-map */}
            {visibleMapId === a.id && (
              <div
                style={{
                  border: "1px solid #e5e7eb",
                  borderTop: "1px solid #f3f4f6",
                  borderRadius: "0 0 8px 8px",
                  overflow: "hidden",
                }}
              >
                {mapLoading ? (
                  <p style={{ padding: "1rem", color: "#6b7280", fontSize: "0.8125rem" }}>Loading map...</p>
                ) : mapData && Array.isArray(mapData.features) && (() => {
                  const bounds = getBoundsFromGeoJSON(mapData);
                  if (!bounds) return null;
                  return (
                    <MapContainer
                      bounds={bounds}
                      style={{ height: isMobile ? "180px" : "240px", width: "100%" }}
                      scrollWheelZoom={false}
                    >
                      <TileLayer url={TILE_URL} attribution='&copy; <a href="https://carto.com/">CARTO</a>' />
                      {mapData.features.map((f, i) => (
                        <GeoJSON key={i} data={f} style={{ color: "#3b82f6", weight: 3, opacity: 0.85 }} />
                      ))}
                    </MapContainer>
                  );
                })()}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "0.75rem",
            marginTop: "1rem",
          }}
        >
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1 || loading}
            style={{
              padding: "6px 14px",
              borderRadius: "6px",
              border: "1px solid #d1d5db",
              background: page <= 1 ? "#f3f4f6" : "#fff",
              cursor: page <= 1 ? "default" : "pointer",
              fontSize: "0.8125rem",
            }}
          >
            Previous
          </button>
          <span style={{ fontSize: "0.8125rem", color: "#6b7280" }}>
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages || loading}
            style={{
              padding: "6px 14px",
              borderRadius: "6px",
              border: "1px solid #d1d5db",
              background: page >= totalPages ? "#f3f4f6" : "#fff",
              cursor: page >= totalPages ? "default" : "pointer",
              fontSize: "0.8125rem",
            }}
          >
            Next
          </button>
        </div>
      )}

      <div style={{ textAlign: "center", fontSize: "0.75rem", color: "#9ca3af", marginTop: "0.5rem" }}>
        {data.total} activities total
      </div>
    </div>
  );
}
