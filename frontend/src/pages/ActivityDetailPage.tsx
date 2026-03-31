/**
 * ActivityDetailPage — full activity view at /profile/activity/:id.
 *
 * Shows activity info and GPS trace on a Leaflet map.
 */

import { useEffect, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { MapContainer, TileLayer, GeoJSON } from "react-leaflet";
import { activitiesApi } from "@/api/client";
import { useAppStore } from "@/store";
import { useIsMobile } from "@/hooks/useIsMobile";
import type { ActivityDetail } from "@/types/api";
import type { LatLngBoundsExpression } from "leaflet";
import "leaflet/dist/leaflet.css";

const TILE_URL = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";

function formatDistance(meters: number): string {
  if (meters >= 1000) return `${(meters / 1000).toFixed(2)} km`;
  return `${Math.round(meters)} m`;
}

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m ${s}s`;
}

function formatPace(paceMinPerKm: number | null | undefined): string {
  if (!paceMinPerKm) return "—";
  const minutes = Math.floor(paceMinPerKm);
  const seconds = Math.round((paceMinPerKm - minutes) * 60);
  return `${minutes}:${String(seconds).padStart(2, "0")} /km`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

function getBounds(coords: [number, number][]): LatLngBoundsExpression | undefined {
  if (!coords.length) return undefined;
  let minLat = Infinity,
    maxLat = -Infinity,
    minLng = Infinity,
    maxLng = -Infinity;
  for (const [lng, lat] of coords) {
    if (lat < minLat) minLat = lat;
    if (lat > maxLat) maxLat = lat;
    if (lng < minLng) minLng = lng;
    if (lng > maxLng) maxLng = lng;
  }
  return [
    [minLat - 0.002, minLng - 0.002],
    [maxLat + 0.002, maxLng + 0.002],
  ];
}

export default function ActivityDetailPage() {
  const { id } = useParams<{ id: string }>();
  const isAuthenticated = useAppStore((s) => s.isAuthenticated);
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const [activity, setActivity] = useState<ActivityDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated) navigate("/");
  }, [isAuthenticated, navigate]);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    activitiesApi
      .get(Number(id))
      .then(setActivity)
      .catch((e) => setError(e.message || "Failed to load activity"))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div style={{ maxWidth: "900px", margin: "0 auto", padding: "2rem 1rem" }}>
        <p style={{ color: "#6b7280" }}>Loading activity...</p>
      </div>
    );
  }

  if (error || !activity) {
    return (
      <div style={{ maxWidth: "900px", margin: "0 auto", padding: "2rem 1rem" }}>
        <Link to="/profile" style={{ color: "#3b82f6", fontSize: "0.875rem" }}>
          ← Back to Profile
        </Link>
        <p style={{ color: "#b91c1c", marginTop: "1rem" }}>{error || "Activity not found"}</p>
      </div>
    );
  }

  const bounds = activity.gps_trace ? getBounds(activity.gps_trace.coordinates) : undefined;

  const geojsonFeature = activity.gps_trace
    ? {
        type: "Feature" as const,
        properties: {},
        geometry: activity.gps_trace,
      }
    : null;

  return (
    <div style={{ maxWidth: "900px", margin: "0 auto", padding: isMobile ? "1rem 0.75rem" : "2rem 1rem" }}>
      <Link to="/profile" style={{ color: "#3b82f6", fontSize: "0.875rem", textDecoration: "none" }}>
        ← Back to Profile
      </Link>

      <h1 style={{ fontSize: "1.5rem", fontWeight: 700, marginTop: "0.75rem", marginBottom: "0.25rem" }}>
        {activity.name}
      </h1>
      <p style={{ color: "#6b7280", fontSize: "0.875rem", marginBottom: "1.5rem" }}>
        {activity.sport_type} &middot; {formatDate(activity.start_date)}
        {activity.city_name ? ` &middot; ${activity.city_name}` : ""}
      </p>

      {/* Stats row */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: isMobile ? "repeat(2, 1fr)" : "repeat(4, 1fr)",
          gap: "1rem",
          marginBottom: "1.5rem",
        }}
      >
        <div>
          <div style={{ fontSize: "0.75rem", color: "#6b7280" }}>Distance</div>
          <div style={{ fontSize: "1.25rem", fontWeight: 600 }}>{formatDistance(activity.distance_meters)}</div>
        </div>
        <div>
          <div style={{ fontSize: "0.75rem", color: "#6b7280" }}>Duration</div>
          <div style={{ fontSize: "1.25rem", fontWeight: 600 }}>{formatDuration(activity.duration_seconds)}</div>
        </div>
        <div>
          <div style={{ fontSize: "0.75rem", color: "#6b7280" }}>Moving Time</div>
          <div style={{ fontSize: "1.25rem", fontWeight: 600 }}>{formatDuration(activity.moving_time_seconds)}</div>
        </div>
        <div>
          <div style={{ fontSize: "0.75rem", color: "#6b7280" }}>Pace</div>
          <div style={{ fontSize: "1.25rem", fontWeight: 600 }}>{formatPace(activity.pace_min_per_km)}</div>
        </div>
      </div>

      {/* Map */}
      {geojsonFeature && bounds ? (
        <div style={{ borderRadius: "8px", overflow: "hidden", border: "1px solid #e5e7eb" }}>
          <MapContainer
            bounds={bounds}
            style={{ height: isMobile ? "300px" : "400px", width: "100%" }}
            scrollWheelZoom={false}
          >
            <TileLayer url={TILE_URL} attribution='&copy; <a href="https://carto.com/">CARTO</a>' />
            <GeoJSON
              data={geojsonFeature}
              style={{ color: "#3b82f6", weight: 3, opacity: 0.8 }}
            />
          </MapContainer>
        </div>
      ) : (
        <div
          style={{
            padding: "2rem",
            textAlign: "center",
            backgroundColor: "#f9fafb",
            borderRadius: "8px",
            border: "1px solid #e5e7eb",
            color: "#6b7280",
          }}
        >
          No GPS trace available for this activity.
        </div>
      )}

      {/* Metadata */}
      <div style={{ marginTop: "1rem", fontSize: "0.8125rem", color: "#9ca3af" }}>
        {activity.has_gps ? "GPS data available" : "No GPS data"}{" "}
        &middot;{" "}
        {activity.is_on_street ? "On-street activity" : "Off-street activity"}
      </div>
    </div>
  );
}
