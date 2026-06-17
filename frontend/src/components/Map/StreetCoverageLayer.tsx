/**
 * StreetCoverageLayer
 *
 * Renders street segments as colored polylines on the Leaflet map.
 * - Green (#22c55e) = traveled
 * - Red (#ef4444) = untraveled / missing
 */

import { useMemo } from "react";
import { GeoJSON } from "react-leaflet";
import type { GeoJSONFeatureCollection } from "@/types/api";
import type { PathOptions } from "leaflet";

interface StreetCoverageLayerProps {
  data: GeoJSONFeatureCollection | null;
  filter?: "traveled" | "untraveled";
}

const COLORS = {
  traveled: "#22c55e",
  untraveled: "#ef4444",
};

function streetStyle(feature: GeoJSON.Feature | undefined): PathOptions {
  const isTraveled = feature?.properties?.is_traveled ?? false;
  return {
    color: isTraveled ? COLORS.traveled : COLORS.untraveled,
    weight: 3,
    opacity: 0.8,
  };
}

export default function StreetCoverageLayer({ data, filter }: StreetCoverageLayerProps) {
  const filtered = useMemo(() => {
    if (!data) return null;
    if (!filter) return data;
    const wanted = filter === "traveled";
    const features = data.features.filter((f) => (f.properties?.is_traveled ?? false) === wanted);
    return { ...data, features };
  }, [data, filter]);

  const key = useMemo(() => {
    return filtered ? `${filtered.features.length}-${filter ?? "all"}` : "empty";
  }, [filtered, filter]);

  if (!filtered || filtered.features.length === 0) return null;

  return (
    <GeoJSON
      key={key}
      data={filtered as unknown as GeoJSON.GeoJsonObject}
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
