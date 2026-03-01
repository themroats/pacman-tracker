/**
 * MapPage — interactive map with activity overlays, filters, and detail popups.
 */

import { useCallback, useEffect, useState } from "react";
import MapView from "@/components/Map/MapView";
import ActivityLayer from "@/components/Map/ActivityLayer";
import ActivityPopup from "@/components/Map/ActivityPopup";
import FilterPanel from "@/components/ActivityList/FilterPanel";
import SyncStatus from "@/components/SyncStatus";
import { activitiesApi } from "@/api/client";
import { useAppStore } from "@/store";
import type { ActivityDetail, GeoJSONFeatureCollection } from "@/types/api";

export default function MapPage() {
  const filters = useAppStore((s) => s.filters);
  const setFilters = useAppStore((s) => s.setFilters);
  const activitiesGeoJSON = useAppStore((s) => s.activitiesGeoJSON);
  const setActivitiesGeoJSON = useAppStore((s) => s.setActivitiesGeoJSON);
  const isAuthenticated = useAppStore((s) => s.isAuthenticated);
  const setLoading = useAppStore((s) => s.setLoading);
  const setError = useAppStore((s) => s.setError);

  const [selectedActivity, setSelectedActivity] = useState<ActivityDetail | null>(null);
  const [popupPosition, setPopupPosition] = useState<[number, number] | null>(null);

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
          const [lng, lat] = detail.gps_trace.coordinates[0];
          setPopupPosition([lat, lng]);
        }
      } catch {
        // Ignore click errors
      }
    },
    [],
  );

  return (
    <div style={{ height: "100vh", width: "100%", position: "relative" }}>
      {/* Filter panel overlay */}
      <div style={{ position: "absolute", top: 10, left: 10, zIndex: 1000, maxWidth: "90%" }}>
        <FilterPanel filters={filters} onFiltersChange={setFilters} />
      </div>

      {/* Sync status overlay */}
      <div style={{ position: "absolute", top: 10, right: 10, zIndex: 1000 }}>
        <SyncStatus />
      </div>

      {/* Map */}
      <MapView>
        <ActivityLayer data={activitiesGeoJSON} onFeatureClick={handleFeatureClick} />
        <ActivityPopup
          activity={selectedActivity}
          position={popupPosition}
          onClose={() => {
            setSelectedActivity(null);
            setPopupPosition(null);
          }}
        />
      </MapView>
    </div>
  );
}
