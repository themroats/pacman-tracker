/**
 * MapPage — interactive map with activity overlays, filters, and detail popups.
 */

import { useCallback, useEffect, useState } from "react";
import MapView from "@/components/Map/MapView";
import ActivityLayer from "@/components/Map/ActivityLayer";
import ActivityPopup from "@/components/Map/ActivityPopup";
import FilterPanel from "@/components/ActivityList/FilterPanel";
import LayerToggles, { type LayerToggle } from "@/components/Map/LayerToggles";
import SyncStatus from "@/components/SyncStatus";
import { activitiesApi } from "@/api/client";
import { useAppStore } from "@/store";
import { useIsMobile } from "@/hooks/useIsMobile";
import type { ActivityDetail } from "@/types/api";

export default function MapPage() {
  const isMobile = useIsMobile();
  const filters = useAppStore((s) => s.filters);
  const setFilters = useAppStore((s) => s.setFilters);
  const activitiesGeoJSON = useAppStore((s) => s.activitiesGeoJSON);
  const setActivitiesGeoJSON = useAppStore((s) => s.setActivitiesGeoJSON);
  const isAuthenticated = useAppStore((s) => s.isAuthenticated);
  const setLoading = useAppStore((s) => s.setLoading);
  const setError = useAppStore((s) => s.setError);

  const [selectedActivity, setSelectedActivity] = useState<ActivityDetail | null>(null);
  const [popupPosition, setPopupPosition] = useState<[number, number] | null>(null);
  const [hasFittedActivities, setHasFittedActivities] = useState(false);

  const [showActivities, setShowActivities] = useState(true);
  const mapLayers: LayerToggle[] = [
    { key: "activities", label: "Activities", color: "#ff4444", enabled: showActivities },
  ];
  const toggleMapLayer = useCallback((key: string) => {
    if (key === "activities") setShowActivities((v) => !v);
  }, []);

  // Fetch activities GeoJSON
  useEffect(() => {
    if (!isAuthenticated) return;

    setLoading(true);
    activitiesApi
      .getAllGeoJSON(filters)
      .then((data) => {
        setActivitiesGeoJSON(data);
        setError(null);
      })
      .catch((err) => {
        setError(err.message || "Failed to load activities");
      })
      .finally(() => setLoading(false));
  }, [isAuthenticated, filters, setActivitiesGeoJSON, setLoading, setError]);

  const handleFeatureClick = useCallback(
    async (activityId: number) => {
      try {
        const detail = await activitiesApi.get(activityId);
        setSelectedActivity(detail);
        // Try to extract a position from the GPS trace
        if (detail.gps_trace && detail.gps_trace.coordinates?.length > 0) {
          const coord = detail.gps_trace.coordinates[0];
          if (coord) {
            const [lng, lat] = coord;
            setPopupPosition([lat, lng]);
          }
        }
      } catch {
        // Ignore click errors
      }
    },
    [],
  );

  return (
    <div style={{ height: "100%", width: "100%", position: "relative", overflow: "hidden" }}>
      {/* Filter panel overlay */}
      <div style={{ position: "absolute", top: 10, left: 50, zIndex: 1001, maxWidth: isMobile ? "calc(100% - 60px)" : "80%" }}>
        <FilterPanel filters={filters} onFiltersChange={setFilters} />
      </div>

      {/* Sync status overlay */}
      <div style={{ position: "absolute", top: isMobile ? 54 : 10, right: 10, zIndex: isMobile ? 999 : 1000, maxWidth: isMobile ? "calc(100% - 20px)" : undefined }}>
        <SyncStatus />
      </div>

      {/* Map */}
      <MapView>
        {showActivities && (
          <ActivityLayer data={activitiesGeoJSON} onFeatureClick={handleFeatureClick} autoFit={!hasFittedActivities} onFit={() => setHasFittedActivities(true)} />
        )}
        <ActivityPopup
          activity={selectedActivity}
          position={popupPosition}
          onClose={() => {
            setSelectedActivity(null);
            setPopupPosition(null);
          }}
        />
      </MapView>
      <LayerToggles layers={mapLayers} onToggle={toggleMapLayer} />
    </div>
  );
}
