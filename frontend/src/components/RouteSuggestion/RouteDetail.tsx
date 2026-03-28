/**
 * T062 — RouteDetail
 *
 * Displays route statistics and segment breakdown.
 */

import type { RouteSegment, GeoJSONLineString } from "@/types/api";
import { useIsMobile } from "@/hooks/useIsMobile";
import { routesApi } from "@/api/client";
import { useState } from "react";

interface RouteInfo {
  id: number;
  distance_meters: number;
  estimated_duration_seconds: number;
  untraveled_distance_meters: number;
  untraveled_ratio: number;
  geometry: GeoJSONLineString;
}

interface RouteDetailProps {
  route: RouteInfo | null;
  segments: RouteSegment[];
  message?: string | null;
}

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

/** Download a GPX file. On iOS, tapping the download triggers "Open in…" with OsmAnd/Coros. */
async function shareOrDownloadGpx(routeId: number): Promise<void> {
  const file = await routesApi.fetchGpx(routeId);

  const url = URL.createObjectURL(file);
  const a = document.createElement("a");
  a.href = url;
  a.download = file.name;
  a.click();
  URL.revokeObjectURL(url);
}

export default function RouteDetail({ route, segments, message }: RouteDetailProps) {
  const isMobile = useIsMobile();
  const [exporting, setExporting] = useState(false);
  if (message && !route) {
    return (
      <div style={{ padding: "1rem", color: "#6b7280" }}>
        <p>{message}</p>
      </div>
    );
  }

  if (!route) {
    return (
      <div style={{ padding: "1rem", color: "#6b7280" }}>
        <p>Configure a route and click &quot;Suggest Route&quot;.</p>
      </div>
    );
  }

  return (
    <div style={{ padding: "1rem" }}>
      {/* Summary stats */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem", marginBottom: "1rem" }}>
        <div>
          <div style={{ fontSize: "0.75rem", color: "#6b7280" }}>Distance</div>
          <div style={{ fontSize: "1.25rem", fontWeight: 700 }}>
            {(route.distance_meters / 1000).toFixed(1)} km
          </div>
        </div>
        <div>
          <div style={{ fontSize: "0.75rem", color: "#6b7280" }}>Duration</div>
          <div style={{ fontSize: "1.25rem", fontWeight: 700 }}>
            {formatDuration(route.estimated_duration_seconds)}
          </div>
        </div>
        <div>
          <div style={{ fontSize: "0.75rem", color: "#6b7280" }}>Untraveled</div>
          <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "#22c55e" }}>
            {(route.untraveled_ratio * 100).toFixed(0)}%
          </div>
        </div>
        <div>
          <div style={{ fontSize: "0.75rem", color: "#6b7280" }}>New streets</div>
          <div style={{ fontSize: "1.25rem", fontWeight: 700 }}>
            {(route.untraveled_distance_meters / 1000).toFixed(1)} km
          </div>
        </div>
      </div>

      {/* Export GPX */}
      <button
        onClick={async () => {
          if (!route) return;
          setExporting(true);
          try {
            await shareOrDownloadGpx(route.id);
          } catch {
            // error is visible via global error handler
          } finally {
            setExporting(false);
          }
        }}
        disabled={exporting}
        style={{
          width: "100%",
          padding: "0.5rem",
          marginBottom: "1rem",
          background: "#4f46e5",
          color: "white",
          border: "none",
          borderRadius: "6px",
          cursor: exporting ? "wait" : "pointer",
          fontSize: "0.875rem",
          fontWeight: 600,
          opacity: exporting ? 0.6 : 1,
        }}
      >
        {exporting ? "Exporting…" : "📤 Export GPX"}
      </button>

      {/* Segments */}
      {segments.length > 0 && (
        <>
          <h4 style={{ fontSize: "0.875rem", marginBottom: "0.5rem" }}>Segments</h4>
          <div style={{ maxHeight: isMobile ? "150px" : "200px", overflowY: "auto" }}>
            {segments.map((s, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  padding: "4px 0",
                  borderBottom: "1px solid #f3f4f6",
                  fontSize: "0.8125rem",
                }}
              >
                <span>
                  {s.is_untraveled && (
                    <span style={{ color: "#22c55e", marginRight: "4px" }}>●</span>
                  )}
                  {s.street_name}
                </span>
                <span style={{ color: "#6b7280" }}>{Math.round(s.length_meters)}m</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
