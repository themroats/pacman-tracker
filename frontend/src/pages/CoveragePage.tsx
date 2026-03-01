/**
 * T052 — CoveragePage
 *
 * Full-featured street coverage dashboard:
 * - City / neighborhood selectors
 * - Map with street coverage layer + neighborhood boundaries
 * - Coverage summary panel
 */

import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MapContainer, TileLayer } from "react-leaflet";
import StreetCoverageLayer from "@/components/Map/StreetCoverageLayer";
import NeighborhoodLayer, {
  type NeighborhoodFeature,
} from "@/components/Map/NeighborhoodLayer";
import CoverageSummary from "@/components/CoverageDashboard/CoverageSummary";
import AreaSelector from "@/components/CoverageDashboard/AreaSelector";
import { useAppStore } from "@/store";
import { citiesApi, coverageApi } from "@/api/client";
import type {
  CityCoverageResponse,
  GeoJSONFeatureCollection,
  NeighborhoodListItem,
} from "@/types/api";

export default function CoveragePage() {
  const navigate = useNavigate();
  const {
    isAuthenticated,
    cities,
    setCities,
    neighborhoods,
    setNeighborhoods,
    selectedCityId,
    setSelectedCity,
    selectedNeighborhoodId,
    setSelectedNeighborhood,
  } = useAppStore();

  const [coverageData, setCoverageData] = useState<CityCoverageResponse | null>(null);
  const [streetsGeoJSON, setStreetsGeoJSON] = useState<GeoJSONFeatureCollection | null>(null);
  const [neighborhoodFeatures, setNeighborhoodFeatures] = useState<NeighborhoodFeature[]>([]);
  const [loading, setLoading] = useState(false);

  // Redirect if not authenticated
  useEffect(() => {
    if (!isAuthenticated) navigate("/");
  }, [isAuthenticated, navigate]);

  // Load cities on mount
  useEffect(() => {
    citiesApi.list().then((r) => setCities(r.cities)).catch(() => {});
  }, [setCities]);

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
    Promise.all([
      coverageApi.city(selectedCityId),
      coverageApi.cityStreets(selectedCityId, {
        neighborhood_id: selectedNeighborhoodId ?? undefined,
      }),
    ])
      .then(([cov, streets]) => {
        setCoverageData(cov);
        setStreetsGeoJSON(streets);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [selectedCityId, selectedNeighborhoodId]);

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
    <div style={{ display: "flex", height: "100vh", width: "100%" }}>
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
          />
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
      <div style={{ flex: 1 }}>
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
          <StreetCoverageLayer data={streetsGeoJSON} />
          <NeighborhoodLayer
            features={neighborhoodFeatures}
            selectedId={selectedNeighborhoodId}
            onSelect={handleNeighborhoodSelect}
          />
        </MapContainer>
      </div>
    </div>
  );
}
