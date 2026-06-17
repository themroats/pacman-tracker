/**
 * NeighborhoodLayer
 *
 * Renders neighborhood boundary polygons on the Leaflet map.
 * Supports click-to-select behaviour.
 */

import { useMemo } from "react";
import { GeoJSON } from "react-leaflet";
import type { PathOptions } from "leaflet";

export interface NeighborhoodFeature {
  type: "Feature";
  properties: {
    id: number;
    name: string;
    coverage_percentage: number;
  };
  geometry: {
    type: string;
    coordinates: number[][][];
  };
}

interface NeighborhoodLayerProps {
  features: NeighborhoodFeature[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}

function neighborhoodStyle(
  feature: GeoJSON.Feature | undefined,
  selectedId: number | null,
): PathOptions {
  const isSelected = feature?.properties?.id === selectedId;
  return {
    color: isSelected ? "#d97706" : "#9ca3af",
    weight: isSelected ? 3 : 1,
    fillColor: isSelected ? "#d9770640" : "transparent",
    fillOpacity: isSelected ? 0.15 : 0,
    dashArray: isSelected ? undefined : "4 4",
  };
}

export default function NeighborhoodLayer({
  features,
  selectedId,
  onSelect,
}: NeighborhoodLayerProps) {
  const featureCollection = useMemo(
    () => ({
      type: "FeatureCollection" as const,
      features,
    }),
    [features],
  );

  const key = useMemo(
    () => `neighborhoods-${features.length}-${selectedId}`,
    [features.length, selectedId],
  );

  if (features.length === 0) return null;

  return (
    <GeoJSON
      key={key}
      data={featureCollection as unknown as GeoJSON.GeoJsonObject}
      style={(f) => neighborhoodStyle(f, selectedId)}
      onEachFeature={(feature, layer) => {
        const p = feature.properties;
        if (p) {
          layer.bindTooltip(
            `<strong>${p.name}</strong><br/>${p.coverage_percentage?.toFixed(1) ?? 0}% covered`,
            { sticky: true },
          );
          layer.on("click", () => onSelect(p.id));
        }
      }}
    />
  );
}
