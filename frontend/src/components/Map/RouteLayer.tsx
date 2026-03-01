/**
 * T061 — RouteLayer
 *
 * Renders a suggested route on the Leaflet map.
 * Untraveled segments are highlighted in a contrasting color.
 */

import React from "react";
import { GeoJSON } from "react-leaflet";
import type { PathOptions } from "leaflet";

interface RouteLayerProps {
  geometry: {
    type: string;
    coordinates: [number, number][];
  } | null;
}

const ROUTE_STYLE: PathOptions = {
  color: "#6366f1",
  weight: 5,
  opacity: 0.85,
  dashArray: "10 6",
};

export default function RouteLayer({ geometry }: RouteLayerProps) {
  if (!geometry || !geometry.coordinates || geometry.coordinates.length < 2) {
    return null;
  }

  const geoJSON = {
    type: "Feature" as const,
    properties: {},
    geometry,
  };

  return (
    <GeoJSON
      key={JSON.stringify(geometry.coordinates.length)}
      data={geoJSON as unknown as GeoJSON.GeoJsonObject}
      style={() => ROUTE_STYLE}
    />
  );
}
