/**
 * ActivityLayer — renders GeoJSON FeatureCollection as colored Polylines on the map.
 */

import { GeoJSON, useMap } from "react-leaflet";
import type { GeoJSONFeatureCollection } from "@/types/api";
import type { PathOptions } from "leaflet";
import { useCallback, useEffect, useRef } from "react";

const SPORT_COLORS: Record<string, string> = {
  Run: "#ff4444",
  Walk: "#44aaff",
  Ride: "#44cc44",
  Hike: "#cc8844",
  default: "#8844cc",
};

interface ActivityLayerProps {
  data: GeoJSONFeatureCollection | null;
  onFeatureClick?: (activityId: number) => void;
  /** Override color for all traces (ignores sport-type colors). */
  color?: string;
  /** Auto-fit map to data bounds when data changes. Default true. */
  autoFit?: boolean;
}

export default function ActivityLayer({ data, onFeatureClick, color, autoFit = true }: ActivityLayerProps) {
  const map = useMap();

  const style = useCallback((feature: any): PathOptions => {
    if (color) {
      return { color, weight: 3, opacity: 0.7 };
    }
    const sportType = feature?.properties?.sport_type || "default";
    return {
      color: SPORT_COLORS[sportType] || SPORT_COLORS.default,
      weight: 3,
      opacity: 0.8,
    };
  }, [color]);

  const onEachFeature = useCallback(
    (feature: any, layer: any) => {
      if (onFeatureClick && feature?.properties?.id) {
        layer.on("click", () => onFeatureClick(feature.properties.id));
      }
    },
    [onFeatureClick],
  );

  // Fit bounds only on initial data load, not on filter changes
  const hasFitted = useRef(false);

  useEffect(() => {
    if (!autoFit) return;
    if (hasFitted.current) return;
    if (data && data.features.length > 0) {
      try {
        const L = (window as any).L;
        if (L) {
          const geojsonLayer = L.geoJSON(data);
          const bounds = geojsonLayer.getBounds();
          if (bounds.isValid()) {
            map.fitBounds(bounds, { padding: [20, 20] });
            hasFitted.current = true;
          }
        }
      } catch {
        // Bounds calculation failed — ignore
      }
    }
  }, [data, map, autoFit]);

  if (!data || data.features.length === 0) {
    return null;
  }

  return (
    <GeoJSON
      key={JSON.stringify(data).slice(0, 100)} // force re-render on data change
      data={data as any}
      style={style}
      onEachFeature={onEachFeature}
    />
  );
}
