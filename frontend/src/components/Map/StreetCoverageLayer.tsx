/**
 * T048 — StreetCoverageLayer
 *
 * Renders street segments as colored polylines on the Leaflet map.
 * - Green (#22c55e) = traveled
 * - Grey (#9ca3af) = untraveled
 */

import React, { useMemo } from "react";
import { GeoJSON, useMap } from "react-leaflet";
import type { GeoJSONFeatureCollection } from "@/types/api";
import type { PathOptions } from "leaflet";

interface StreetCoverageLayerProps {
  data: GeoJSONFeatureCollection | null;
}

const COLORS = {
  traveled: "#22c55e",
  untraveled: "#9ca3af",
};

function streetStyle(feature: GeoJSON.Feature | undefined): PathOptions {
  const isTraveled = feature?.properties?.is_traveled ?? false;
  return {
    color: isTraveled ? COLORS.traveled : COLORS.untraveled,
    weight: 3,
    opacity: 0.8,
  };
}

export default function StreetCoverageLayer({ data }: StreetCoverageLayerProps) {
  const map = useMap();

  const key = useMemo(() => {
    // Force re-render when data changes
    return data ? JSON.stringify(data.features.length) : "empty";
  }, [data]);

  if (!data || data.features.length === 0) return null;

  return (
    <GeoJSON
      key={key}
      data={data as unknown as GeoJSON.GeoJsonObject}
      style={streetStyle}
      onEachFeature={(feature, layer) => {
        const p = feature.properties;
        if (p) {
          const status = p.is_traveled ? "Traveled" : "Untraveled";
          const ratio = ((p.coverage_ratio ?? 0) * 100).toFixed(0);
          layer.bindTooltip(
            `<strong>${p.name || "Unnamed"}</strong><br/>${status} (${ratio}%)`,
            { sticky: true },
          );
        }
      }}
    />
  );
}
