/**
 * T052 — CoveragePage
 *
 * Full-featured street coverage dashboard:
 * - City / neighborhood selectors
 * - Map with street coverage layer + neighborhood boundaries
 * - Coverage summary panel
 */

import { useCallback, useEffect, useRef, useState } from "react";
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
import { citiesApi, coverageApi, activitiesApi, syncApi, ApiClientError } from "@/api/client";
import { useCityCatalog } from "@/hooks/useCityCatalog";
import type {
  CityCoverageResponse,
  GeoJSONFeatureCollection,
  SyncStatusResponse,
} from "@/types/api";

function isCoverageJobActive(status: string | undefined): boolean {
  return status === "importing" || status === "syncing";
}

function formatLastCoverageRun(lastSyncAt: string | null): string {
  if (!lastSyncAt) return "Not yet run";

  const timestamp = new Date(lastSyncAt);
  if (Number.isNaN(timestamp.getTime())) return "Not yet run";

  return timestamp.toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function buildCoverageProgressMessage(status: SyncStatusResponse): string | null {
  if (status.status === "error") {
    return status.error_message || "Coverage matching failed. Please try again.";
  }

  if (!isCoverageJobActive(status.status)) {
    return status.last_sync_at ? "Coverage data is up to date." : null;
  }

  if (status.imported_activities <= 0) {
    return "Preparing imported activities for coverage matching.";
  }

  return `Matched ${status.matched_activities} of ${status.imported_activities} imported activities.`;
}

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
  const streetsCache = useRef<Map<string, GeoJSONFeatureCollection>>(new Map());
  const [activitiesGeoJSON, setActivitiesGeoJSON] = useState<GeoJSONFeatureCollection | null>(null);
  const [neighborhoodFeatures, setNeighborhoodFeatures] = useState<NeighborhoodFeature[]>([]);
  const [loading, setLoading] = useState(false);
  const [coverageStatus, setCoverageStatus] = useState<SyncStatusResponse | null>(null);
  const [coverageJobMessage, setCoverageJobMessage] = useState<string | null>(null);
  const [coverageJobError, setCoverageJobError] = useState<string | null>(null);
  const [lastCoverageRunLabel, setLastCoverageRunLabel] = useState<string>("Not yet run");
  const previousCoverageStatus = useRef<string | null>(null);

  const coverageJobRunning = isCoverageJobActive(coverageStatus?.status);
  const coverageCompletionPercent = coverageStatus?.imported_activities
    ? Math.min(
        100,
        Math.round((coverageStatus.matched_activities / coverageStatus.imported_activities) * 100),
      )
    : 0;

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

  const loadCoverageData = useCallback(async (cityId: number) => {
    setLoading(true);
    try {
      const data = await coverageApi.city(cityId);
      setCoverageData(data);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadStreetCoverage = useCallback((cityId: number, neighborhoodId: number | null) => {
    const cacheKey = `${cityId}:${neighborhoodId ?? "all"}`;
    const cached = streetsCache.current.get(cacheKey);
    if (cached) {
      setStreetsGeoJSON(cached);
      return Promise.resolve();
    }
    return coverageApi.cityStreets(cityId, {
      neighborhood_id: neighborhoodId ?? undefined,
    }).then((data) => {
      streetsCache.current.set(cacheKey, data);
      setStreetsGeoJSON(data);
    });
  }, []);

  const loadCityActivities = useCallback((cityId: number) => {
    return activitiesApi.getAllGeoJSON({ city_id: cityId }).then(setActivitiesGeoJSON);
  }, []);

  const refreshCoveragePageData = useCallback(async () => {
    if (!selectedCityId) return;

    await Promise.allSettled([
      loadCoverageData(selectedCityId),
      loadStreetCoverage(selectedCityId, selectedNeighborhoodId),
      loadCityActivities(selectedCityId),
    ]);
  }, [loadCityActivities, loadCoverageData, loadStreetCoverage, selectedCityId, selectedNeighborhoodId]);

  const applyCoverageStatus = useCallback((status: SyncStatusResponse) => {
    setCoverageStatus(status);
    setCoverageJobError(status.status === "error" ? status.error_message || "Coverage matching failed. Please try again." : null);
    setCoverageJobMessage(status.status === "error" ? null : buildCoverageProgressMessage(status));
    setLastCoverageRunLabel(formatLastCoverageRun(status.last_sync_at));
  }, []);

  const fetchCoverageStatus = useCallback(async () => {
    const status = await syncApi.status();
    applyCoverageStatus(status);
    return status;
  }, [applyCoverageStatus]);

  // Redirect if not authenticated
  useEffect(() => {
    if (!isAuthenticated) navigate("/");
  }, [isAuthenticated, navigate]);

  useEffect(() => {
    if (!isAuthenticated) {
      setCoverageStatus(null);
      setCoverageJobMessage(null);
      setCoverageJobError(null);
      setLastCoverageRunLabel("Not yet run");
      previousCoverageStatus.current = null;
      return;
    }

    fetchCoverageStatus();
  }, [fetchCoverageStatus, isAuthenticated]);

  // Load neighborhoods when city changes
  useEffect(() => {
    if (!selectedCityId) {
      setNeighborhoods([]);
      return;
    }
    citiesApi
      .neighborhoods(selectedCityId)
      .then((r) => setNeighborhoods(r.neighborhoods))
      ;
  }, [selectedCityId, setNeighborhoods]);

  // Load coverage data when city changes
  useEffect(() => {
    if (!selectedCityId) {
      setCoverageData(null);
      setStreetsGeoJSON(null);
      setNeighborhoodFeatures([]);
      streetsCache.current.clear();
      return;
    }
    streetsCache.current.clear();
    loadCoverageData(selectedCityId)
      
      .finally(() => {});
  }, [loadCoverageData, selectedCityId]);

  // Load streets when city or neighborhood changes
  useEffect(() => {
    if (!selectedCityId) {
      setStreetsGeoJSON(null);
      return;
    }
    loadStreetCoverage(selectedCityId, selectedNeighborhoodId)
      ;
  }, [loadStreetCoverage, selectedCityId, selectedNeighborhoodId]);

  // Load activities separately (only depends on city)
  useEffect(() => {
    if (!selectedCityId) {
      setActivitiesGeoJSON(null);
      return;
    }
    loadCityActivities(selectedCityId)
      ;
  }, [loadCityActivities, selectedCityId]);

  // Load neighborhood boundaries
  useEffect(() => {
    if (!selectedCityId || neighborhoods.length === 0) {
      setNeighborhoodFeatures([]);
      return;
    }
    citiesApi.neighborhoodBoundaries(selectedCityId)
      .then((response) => setNeighborhoodFeatures(response.features as NeighborhoodFeature[]))
      ;
  }, [selectedCityId, neighborhoods]);

  const handleNeighborhoodSelect = useCallback(
    (id: number) => {
      setSelectedNeighborhood(id === selectedNeighborhoodId ? null : id);
    },
    [selectedNeighborhoodId, setSelectedNeighborhood],
  );

  useEffect(() => {
    if (!isAuthenticated || !coverageJobRunning) return;

    const timer = window.setInterval(() => {
      fetchCoverageStatus();
    }, 2000);

    return () => {
      window.clearInterval(timer);
    };
  }, [coverageJobRunning, fetchCoverageStatus, isAuthenticated]);

  useEffect(() => {
    const previousStatus = previousCoverageStatus.current;
    const currentStatus = coverageStatus?.status ?? null;

    if (previousStatus && isCoverageJobActive(previousStatus) && currentStatus === "idle") {
      setCoverageJobMessage("Coverage data updated.");
      refreshCoveragePageData();
    }

    previousCoverageStatus.current = currentStatus;
  }, [coverageStatus?.status, refreshCoveragePageData]);

  const handleRunCoverage = useCallback(async () => {
    if (!selectedCityId || coverageJobRunning) return;

    setCoverageJobError(null);
    setCoverageJobMessage("Coverage matching started. This may take a few minutes.");

    try {
      await syncApi.triggerCoverage();
      await fetchCoverageStatus();
    } catch (error) {
      if (error instanceof ApiClientError) {
        setCoverageJobError(error.message);
      } else {
        setCoverageJobError("Coverage matching failed. Please try again.");
      }
    }
  }, [coverageJobRunning, fetchCoverageStatus, selectedCityId]);

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
          <div
            style={{
              marginTop: "0.75rem",
              padding: "0.75rem",
              border: "1px solid #e5e7eb",
              borderRadius: "8px",
              backgroundColor: "#f8fafc",
            }}
          >
            <div style={{ fontSize: "0.875rem", fontWeight: 600, color: "#111827" }}>
              Coverage Processing
            </div>
            <p style={{ margin: "0.35rem 0 0", fontSize: "0.8125rem", color: "#4b5563", lineHeight: 1.45 }}>
              Processes your imported GPS activities and updates street coverage for your account.
            </p>
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginTop: "0.75rem", flexWrap: "wrap" }}>
              <button
                onClick={handleRunCoverage}
                disabled={!selectedCityId || coverageJobRunning || !isAuthenticated}
                style={{
                  padding: "8px 12px",
                  backgroundColor: coverageJobRunning ? "#93c5fd" : "#2563eb",
                  color: "#fff",
                  border: "none",
                  borderRadius: "6px",
                  cursor: !selectedCityId || coverageJobRunning || !isAuthenticated ? "not-allowed" : "pointer",
                  fontSize: "0.8125rem",
                  fontWeight: 600,
                }}
              >
                {coverageJobRunning ? "Running Coverage Matching..." : "Run Coverage Matching"}
              </button>
              <span style={{ fontSize: "0.75rem", color: "#6b7280" }}>
                Last run: {lastCoverageRunLabel}
              </span>
            </div>
            {coverageJobRunning && (
              <>
                <div
                  aria-label="Coverage processing progress"
                  style={{
                    marginTop: "0.75rem",
                    width: "100%",
                    height: "8px",
                    borderRadius: "999px",
                    backgroundColor: "#dbeafe",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      width: `${coverageCompletionPercent}%`,
                      height: "100%",
                      backgroundColor: "#2563eb",
                      transition: "width 0.3s ease",
                    }}
                  />
                </div>
                <p style={{ margin: "0.5rem 0 0", fontSize: "0.75rem", color: "#4b5563" }}>
                  {coverageStatus?.imported_activities ?? 0} imported activities • {coverageStatus?.matched_activities ?? 0} matched
                </p>
              </>
            )}
            {coverageJobMessage && !coverageJobError && (
              <p style={{ margin: "0.5rem 0 0", fontSize: "0.75rem", color: "#1d4ed8" }}>
                {coverageJobMessage}
              </p>
            )}
            {coverageJobError && (
              <p style={{ margin: "0.5rem 0 0", fontSize: "0.75rem", color: "#b91c1c" }}>
                {coverageJobError}
              </p>
            )}
          </div>
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
