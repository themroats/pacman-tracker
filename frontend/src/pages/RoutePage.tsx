/**
 * RoutePage — full route suggestion page.
 *
 * Sidebar with RouteForm + RouteDetail, main map with RouteLayer.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MapContainer, TileLayer } from "react-leaflet";
import RouteForm from "@/components/RouteSuggestion/RouteForm";
import RouteDetail from "@/components/RouteSuggestion/RouteDetail";
import RouteLayer from "@/components/Map/RouteLayer";
import LayerToggles, { type LayerToggle } from "@/components/Map/LayerToggles";
import { routesApi, citiesApi } from "@/api/client";
import { useCityCatalog } from "@/hooks/useCityCatalog";
import { useIsMobile } from "@/hooks/useIsMobile";
import { useAppStore } from "@/store";
import type {
  RouteSuggestResponse,
  RouteSegment,
  GeoJSONLineString,
} from "@/types/api";
import "leaflet/dist/leaflet.css";

const TILE_URL = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";
const DEFAULT_CENTER: [number, number] = [47.6062, -122.3321]; // Seattle
const DEFAULT_ZOOM = 13;

interface RouteInfo {
  id: number;
  distance_meters: number;
  estimated_duration_seconds: number;
  untraveled_distance_meters: number;
  untraveled_ratio: number;
  geometry: GeoJSONLineString;
}

export default function RoutePage() {
  const isAuthenticated = useAppStore((s) => s.isAuthenticated);
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const neighborhoods = useAppStore((s) => s.neighborhoods);
  const setNeighborhoods = useAppStore((s) => s.setNeighborhoods);
  const { cities, isBootstrapping, bootstrapError } = useCityCatalog();

  // Redirect if not authenticated
  useEffect(() => {
    if (!isAuthenticated) navigate("/");
  }, [isAuthenticated, navigate]);

  const [route, setRoute] = useState<RouteInfo | null>(null);
  const [segments, setSegments] = useState<RouteSegment[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [osrmAvailable, setOsrmAvailable] = useState<boolean | null>(null);

  // Check OSRM availability on mount
  useEffect(() => {
    // /health is at the API root, not under /api/v1
    const apiBase = import.meta.env.VITE_API_URL || "/api/v1";
    const healthUrl = apiBase.replace(/\/api\/v1\/?$/, "/health");
    fetch(healthUrl)
      .then((r) => r.json())
      .then((data) => setOsrmAvailable(data.osrm_available ?? null))
      .catch(() => setOsrmAvailable(false));
  }, []);

  const [layerVis, setLayerVis] = useState({ route: true, untraveled: true });
  const toggleLayer = useCallback((key: string) => {
    setLayerVis((prev) => ({ ...prev, [key]: !prev[key as keyof typeof prev] }));
  }, []);
  const routeLayers: LayerToggle[] = [
    { key: "route", label: "Route", color: "#6366f1", enabled: layerVis.route },
    { key: "untraveled", label: "Untraveled streets", color: "#22c55e", enabled: layerVis.untraveled },
  ];

  const handleCityChange = useCallback(
    (cityId: number | null) => {
      if (cityId) {
        citiesApi
          .neighborhoods(cityId)
          .then((r) => setNeighborhoods(r.neighborhoods));
      } else {
        setNeighborhoods([]);
      }
    },
    [setNeighborhoods],
  );

  const handleSubmit = useCallback(
    async (params: {
      start_point: { lng: number; lat: number };
      distance_meters: number;
      city_id: number;
      neighborhood_id?: number;
    }) => {
      setLoading(true);
      setMessage(null);
      try {
        const resp: RouteSuggestResponse = await routesApi.suggest(params);
        setRoute(resp.route ?? null);
        setSegments(resp.segments ?? []);
        setMessage(resp.message ?? null);
      } catch {
        setMessage("Failed to generate route. Please try again.");
        setRoute(null);
        setSegments([]);
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  return (
    <div style={{
      display: "flex",
      flexDirection: isMobile ? "column" : "row",
      height: isMobile ? undefined : "100%",
      width: "100%",
      position: isMobile ? undefined : "absolute",
      inset: isMobile ? undefined : 0,
      overflow: isMobile ? "auto" : undefined,
    }}>
      {/* Sidebar */}
      <div
        style={{
          width: isMobile ? "100%" : "380px",
          overflowY: "auto",
          borderRight: isMobile ? undefined : "1px solid #e5e7eb",
          borderBottom: isMobile ? "1px solid #e5e7eb" : undefined,
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div style={{ padding: "1rem", borderBottom: "1px solid #e5e7eb" }}>
          <h1 style={{ fontSize: "1.25rem", fontWeight: 700, margin: 0 }}>Route Suggestions</h1>
          <p style={{ fontSize: "0.8125rem", color: "#6b7280", marginTop: "0.25rem" }}>
            Generate routes that maximize untraveled streets.
          </p>
        </div>

        <div style={{ padding: "1rem" }}>
          {osrmAvailable === false ? (
            <div style={{ padding: "1rem", background: "#fef2f2", borderRadius: "8px", border: "1px solid #fca5a5" }}>
              <p style={{ color: "#dc2626", fontWeight: 600, margin: 0 }}>Route suggestions unavailable</p>
              <p style={{ color: "#6b7280", fontSize: "0.8125rem", marginTop: "0.25rem" }}>
                The routing service is not running. Route suggestions require OSRM to be started.
              </p>
            </div>
          ) : (
            <RouteForm
              cities={cities}
              neighborhoods={neighborhoods}
              onCityChange={handleCityChange}
              onSubmit={handleSubmit}
              loading={loading}
              citiesLoading={isBootstrapping}
            />
          )}
          {isBootstrapping && cities.length === 0 && (
            <p style={{ marginTop: "0.75rem", fontSize: "0.8125rem", color: "#6b7280" }}>
              Preparing city data for the first run. This can take a minute or two.
            </p>
          )}
          {bootstrapError && cities.length === 0 && (
            <p style={{ marginTop: "0.75rem", fontSize: "0.8125rem", color: "#b91c1c" }}>
              City bootstrap failed: {bootstrapError}
            </p>
          )}
        </div>

        <div style={{ borderTop: "1px solid #e5e7eb", flex: 1 }}>
          <RouteDetail route={route} segments={segments} message={message} />
        </div>
      </div>

      {/* Map */}
      <div style={{ flex: isMobile ? undefined : 1, position: "relative", height: isMobile ? "60vh" : undefined }}>
        <MapContainer
          center={DEFAULT_CENTER}
          zoom={DEFAULT_ZOOM}
          style={{ height: "100%", width: "100%" }}
          preferCanvas
        >
          <TileLayer url={TILE_URL} attribution="&copy; CartoDB" />
          {route && (
            <RouteLayer
              geometry={route.geometry}
              segments={segments}
              showRoute={layerVis.route}
              showUntraveled={layerVis.untraveled}
            />
          )}
        </MapContainer>
        <LayerToggles layers={routeLayers} onToggle={toggleLayer} />
      </div>
    </div>
  );
}
