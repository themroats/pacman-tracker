/**
 * T052 — CoveragePage
 *
 * Full-featured street coverage dashboard:
 * - City / neighborhood selectors
 * - Map with street coverage layer + neighborhood boundaries
 * - Coverage summary panel
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MapContainer, TileLayer } from "react-leaflet";
import StreetCoverageLayer from "@/components/Map/StreetCoverageLayer";
import NeighborhoodLayer, {
  type NeighborhoodFeature,
} from "@/components/Map/NeighborhoodLayer";
import ActivityLayer from "@/components/Map/ActivityLayer";
import LayerToggles, { type LayerToggle } from "@/components/Map/LayerToggles";
import CoverageSummary from "@/components/CoverageDashboard/CoverageSummary";
import AreaSelector from "@/components/CoverageDashboard/AreaSelector";
import { useAppStore } from "@/store";
import { citiesApi, coverageApi, activitiesApi } from "@/api/client";
import { useCityCatalog } from "@/hooks/useCityCatalog";
import type {
  CityCoverageResponse,
  GeoJSONFeatureCollection,
} from "@/types/api";

export default function CoveragePage() {
  const navigate = useNavigate();
  const {
    isAuthenticated,
    neighborhoods,
    setNeighborhoods,
    selectedCityId,
    setSelectedCity,
    selectedNeighborhoodId,
    setSelectedNeighborhood,
  } = useAppStore();
  const { cities, isBootstrapping, bootstrapError } = useCityCatalog();

  const [coverageData, setCoverageData] = useState<CityCoverageResponse | null>(null);
  const [streetsGeoJSON, setStreetsGeoJSON] = useState<GeoJSONFeatureCollection | null>(null);
  const [activitiesGeoJSON, setActivitiesGeoJSON] = useState<GeoJSONFeatureCollection | null>(null);
  const [neighborhoodFeatures, setNeighborhoodFeatures] = useState<NeighborhoodFeature[]>([]);
  const [loading, setLoading] = useState(false);

  const [layerVis, setLayerVis] = useState({ activities: true, traveled: true, untraveled: true, neighborhoods: true });
  const toggleLayer = useCallback((key: string) => {
    setLayerVis((prev) => ({ ...prev, [key]: !prev[key as keyof typeof prev] }));
  }, []);
  const coverageLayers: LayerToggle[] = [
    { key: "activities", label: "Activities", color: "#3b82f6", enabled: layerVis.activities },
    { key: "traveled", label: "Covered streets", color: "#22c55e", enabled: layerVis.traveled },
    { key: "untraveled", label: "Missing streets", color: "#ef4444", enabled: layerVis.untraveled },
    { key: "neighborhoods", label: "Neighborhoods", color: "#9ca3af", enabled: layerVis.neighborhoods },
  ];

  // Redirect if not authenticated
  useEffect(() => {
    if (!isAuthenticated) navigate("/");
  }, [isAuthenticated, navigate]);

  // Load neighborhoods when city changes
  useEffect(() => {
    if (!selectedCityId) {
      setNeighborhoods([]);
      return;
    }
    citiesApi
      .neighborhoods(selectedCityId)
      .then((r) => setNeighborhoods(r.neighborhoods))
      .catch(() => {});
  }, [selectedCityId, setNeighborhoods]);

  // Load coverage data when city changes
  useEffect(() => {
    if (!selectedCityId) {
      setCoverageData(null);
      setStreetsGeoJSON(null);
      setNeighborhoodFeatures([]);
      return;
    }
    setLoading(true);
    coverageApi.city(selectedCityId)
      .then(setCoverageData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [selectedCityId]);

  // Load streets when city or neighborhood changes
  useEffect(() => {
    if (!selectedCityId) {
      setStreetsGeoJSON(null);
      return;
    }
    coverageApi.cityStreets(selectedCityId, {
      neighborhood_id: selectedNeighborhoodId ?? undefined,
    })
      .then(setStreetsGeoJSON)
      .catch(() => {});
  }, [selectedCityId, selectedNeighborhoodId]);

  // Load activities separately (only depends on city)
  useEffect(() => {
    if (!selectedCityId) {
      setActivitiesGeoJSON(null);
      return;
    }
    activitiesApi.getAllGeoJSON({ city_id: selectedCityId })
      .then(setActivitiesGeoJSON)
      .catch(() => {});
  }, [selectedCityId]);

  // Load neighborhood boundaries
  useEffect(() => {
    if (!selectedCityId || neighborhoods.length === 0) {
      setNeighborhoodFeatures([]);
      return;
    }
    // Fetch boundaries for all neighborhoods
    Promise.all(
      neighborhoods.map((n) =>
        citiesApi.neighborhoodBoundary(selectedCityId!, n.id).then((f) => ({
          ...(f as unknown as NeighborhoodFeature),
          properties: {
            id: n.id,
            name: n.name,
            coverage_percentage: n.coverage_percentage,
          },
        })),
      ),
    )
      .then(setNeighborhoodFeatures)
      .catch(() => {});
  }, [selectedCityId, neighborhoods]);

  const handleNeighborhoodSelect = useCallback(
    (id: number) => {
      setSelectedNeighborhood(id === selectedNeighborhoodId ? null : id);
    },
    [selectedNeighborhoodId, setSelectedNeighborhood],
  );

  return (
    <div style={{ display: "flex", height: "100%", width: "100%", position: "absolute", inset: 0 }}>
      {/* Sidebar */}
      <div
        style={{
          width: "360px",
          flexShrink: 0,
          borderRight: "1px solid #e5e7eb",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Area selector */}
        <div style={{ padding: "0.75rem", borderBottom: "1px solid #e5e7eb" }}>
          <AreaSelector
            cities={cities}
            neighborhoods={neighborhoods}
            selectedCityId={selectedCityId}
            selectedNeighborhoodId={selectedNeighborhoodId}
            onCityChange={setSelectedCity}
            onNeighborhoodChange={setSelectedNeighborhood}
            citiesLoading={isBootstrapping}
          />
          {isBootstrapping && cities.length === 0 && (
            <p style={{ margin: "0.5rem 0 0", fontSize: "0.8125rem", color: "#6b7280" }}>
              Preparing city data for the first run. This can take a minute or two.
            </p>
          )}
          {bootstrapError && cities.length === 0 && (
            <p style={{ margin: "0.5rem 0 0", fontSize: "0.8125rem", color: "#b91c1c" }}>
              City bootstrap failed: {bootstrapError}
            </p>
          )}
        </div>

        {/* Coverage summary */}
        <div style={{ flex: 1, overflowY: "auto" }}>
          {loading ? (
            <div style={{ padding: "2rem", textAlign: "center", color: "#6b7280" }}>
              Loading...
            </div>
          ) : (
            <CoverageSummary
              city={coverageData?.city ?? null}
              neighborhoods={coverageData?.neighborhoods ?? []}
              onNeighborhoodClick={handleNeighborhoodSelect}
            />
          )}
        </div>

        {/* Back button */}
        <div style={{ padding: "0.75rem", borderTop: "1px solid #e5e7eb" }}>
          <button
            onClick={() => navigate("/map")}
            style={{
              width: "100%",
              padding: "8px",
              backgroundColor: "#f3f4f6",
              border: "1px solid #d1d5db",
              borderRadius: "6px",
              cursor: "pointer",
              fontSize: "0.875rem",
            }}
          >
            &larr; Back to Map
          </button>
        </div>
      </div>

      {/* Map */}
      <div style={{ flex: 1, position: "relative" }}>
        <MapContainer
          center={[47.6062, -122.3321]}
          zoom={13}
          style={{ height: "100%", width: "100%" }}
          preferCanvas
        >
          <TileLayer
            attribution='&copy; <a href="https://carto.com">CARTO</a>'
            url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
          />
          {layerVis.traveled && <StreetCoverageLayer data={streetsGeoJSON} filter="traveled" />}
          {layerVis.untraveled && <StreetCoverageLayer data={streetsGeoJSON} filter="untraveled" />}
          {layerVis.activities && activitiesGeoJSON && <ActivityLayer data={activitiesGeoJSON} color="#3b82f6" autoFit={false} />}
          {layerVis.neighborhoods && (
            <NeighborhoodLayer
              features={neighborhoodFeatures}
              selectedId={selectedNeighborhoodId}
              onSelect={handleNeighborhoodSelect}
            />
          )}
        </MapContainer>
        <LayerToggles layers={coverageLayers} onToggle={toggleLayer} />
      </div>
    </div>
  );
}
