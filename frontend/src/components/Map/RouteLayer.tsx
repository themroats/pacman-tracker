/**
 * T061 — RouteLayer
 *
 * Renders a suggested route on the Leaflet map.
 * The full OSRM route is shown as a dashed line.
 * Untraveled street segments are overlaid in green to highlight new coverage.
 */

import { useMemo } from "react";
import { GeoJSON } from "react-leaflet";
import type { PathOptions } from "leaflet";
import type { RouteSegment } from "@/types/api";

interface RouteLayerProps {
  geometry: {
    type: string;
    coordinates: [number, number][];
  } | null;
  segments?: RouteSegment[];
  showRoute?: boolean;
  showUntraveled?: boolean;
}

const ROUTE_STYLE: PathOptions = {
  color: "#6366f1",
  weight: 4,
  opacity: 0.6,
  dashArray: "10 6",
};

const UNTRAVELED_STYLE: PathOptions = {
  color: "#22c55e",
  weight: 5,
  opacity: 0.9,
};

export default function RouteLayer({ geometry, segments, showRoute = true, showUntraveled = true }: RouteLayerProps) {
  // Build a FeatureCollection from untraveled segments that have geometry
  const untraveledGeoJSON = useMemo(() => {
    if (!segments) return null;
    const features = segments
      .filter((s) => s.is_untraveled && s.geometry)
      .map((s, i) => ({
        type: "Feature" as const,
        properties: { name: s.street_name, index: i },
        geometry: s.geometry!,
      }));
    if (features.length === 0) return null;
    return { type: "FeatureCollection" as const, features };
  }, [segments]);

  if (!geometry || !geometry.coordinates || geometry.coordinates.length < 2) {
    return null;
  }

  const routeGeoJSON = {
    type: "Feature" as const,
    properties: {},
    geometry,
  };

  // Use coordinate count + segment count as key to force re-render
  const layerKey = `${geometry.coordinates.length}-${segments?.length ?? 0}`;

  return (
    <>
      {showRoute && (
        <GeoJSON
          key={`route-${layerKey}`}
          data={routeGeoJSON as unknown as GeoJSON.GeoJsonObject}
          style={() => ROUTE_STYLE}
        />
      )}
      {showUntraveled && untraveledGeoJSON && (
        <GeoJSON
          key={`untraveled-${layerKey}`}
          data={untraveledGeoJSON as unknown as GeoJSON.GeoJsonObject}
          style={() => UNTRAVELED_STYLE}
        />
      )}
    </>
  );
}
