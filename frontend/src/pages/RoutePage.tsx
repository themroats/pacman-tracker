/**
 * RoutePage — full route suggestion page.
 *
 * Sidebar with RouteForm + RouteDetail, main map with RouteLayer.
 */

import { useCallback, useState } from "react";
import { MapContainer, TileLayer } from "react-leaflet";
import RouteForm from "@/components/RouteSuggestion/RouteForm";
import RouteDetail from "@/components/RouteSuggestion/RouteDetail";
import RouteLayer from "@/components/Map/RouteLayer";
import LayerToggles, { type LayerToggle } from "@/components/Map/LayerToggles";
import { routesApi, citiesApi } from "@/api/client";
import { useCityCatalog } from "@/hooks/useCityCatalog";
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
  const neighborhoods = useAppStore((s) => s.neighborhoods);
  const setNeighborhoods = useAppStore((s) => s.setNeighborhoods);
  const { cities, isBootstrapping, bootstrapError } = useCityCatalog();

  const [route, setRoute] = useState<RouteInfo | null>(null);
  const [segments, setSegments] = useState<RouteSegment[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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
          .then((r) => setNeighborhoods(r.neighborhoods))
          .catch(() => {});
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
    <div style={{ display: "flex", height: "100%", width: "100%", position: "absolute", inset: 0 }}>
      {/* Sidebar */}
      <div
        style={{
          width: "380px",
          overflowY: "auto",
          borderRight: "1px solid #e5e7eb",
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
          <RouteForm
            cities={cities}
            neighborhoods={neighborhoods}
            onCityChange={handleCityChange}
            onSubmit={handleSubmit}
            loading={loading}
            citiesLoading={isBootstrapping}
          />
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
      <div style={{ flex: 1, position: "relative" }}>
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
