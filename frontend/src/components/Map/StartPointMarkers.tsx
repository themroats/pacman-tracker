/**
 * StartPointMarkers — draggable active start pin + saved point markers on the route map.
 *
 * - Blue draggable marker for the current start point
 * - Small gray markers for saved start points (click to select)
 * - MapClickHandler to place the start point on map click
 */

import { useEffect, useMemo } from "react";
import { Marker, Tooltip, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import type { SavedStartPoint } from "@/types/api";

// Fix default Leaflet marker icon paths (Vite doesn't bundle them correctly)
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";

delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

/** Blue pin for the active start point (draggable). */
const activeIcon = new L.Icon({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

/** Small gray circle for saved start points. */
const savedIcon = new L.DivIcon({
  className: "",
  html: `<div style="
    width:12px;height:12px;border-radius:50%;
    background:#6b7280;border:2px solid #fff;
    box-shadow:0 1px 3px rgba(0,0,0,0.3);
  "></div>`,
  iconSize: [12, 12],
  iconAnchor: [6, 6],
});

interface StartPointMarkersProps {
  /** Current active start position [lat, lng] for placing a new point. */
  position: [number, number] | null;
  /** Called when user clicks map or drags the marker. */
  onPositionChange: (latlng: { lat: number; lng: number }) => void;
  /** Saved start points to show on the map. */
  savedPoints: SavedStartPoint[];
  /** Called when user clicks a saved point marker. */
  onSelectSavedPoint: (id: number) => void;
  /** Currently selected saved point ID (to highlight with blue pin). */
  selectedPointId: number | null;
  /** When true, show draggable pin and capture map clicks (add-point mode). */
  interactive: boolean;
}

/** Captures map clicks to place the start point. */
function MapClickHandler({ onPositionChange }: { onPositionChange: (latlng: { lat: number; lng: number }) => void }) {
  useMapEvents({
    click(e) {
      onPositionChange({ lat: e.latlng.lat, lng: e.latlng.lng });
    },
  });
  return null;
}

export default function StartPointMarkers({
  position,
  onPositionChange,
  savedPoints,
  onSelectSavedPoint,
  selectedPointId,
  interactive,
}: StartPointMarkersProps) {
  const map = useMap();

  // Pan to view the active marker when it's first set in add mode
  useEffect(() => {
    if (interactive && position) {
      const bounds = map.getBounds();
      const latlng = L.latLng(position[0], position[1]);
      if (!bounds.contains(latlng)) {
        map.panTo(latlng);
      }
    }
  }, [interactive, position, map]);

  const eventHandlers = useMemo(
    () => ({
      dragend(e: L.DragEndEvent) {
        const marker = e.target as L.Marker;
        const ll = marker.getLatLng();
        onPositionChange({ lat: ll.lat, lng: ll.lng });
      },
    }),
    [onPositionChange],
  );

  return (
    <>
      {interactive && <MapClickHandler onPositionChange={onPositionChange} />}

      {/* Saved point markers */}
      {savedPoints.map((p) => (
        <Marker
          key={p.id}
          position={[p.lat, p.lng]}
          icon={p.id === selectedPointId ? activeIcon : savedIcon}
          eventHandlers={{ click: () => onSelectSavedPoint(p.id) }}
        >
          <Tooltip direction="top" offset={p.id === selectedPointId ? [0, -34] : [0, -6]}>
            {p.name}{p.id === selectedPointId ? " (selected)" : ""}
          </Tooltip>
        </Marker>
      ))}

      {/* Draggable pin for placing a new point (add mode only) */}
      {interactive && position && (
        <Marker
          position={position}
          icon={activeIcon}
          draggable
          eventHandlers={eventHandlers}
        >
          <Tooltip direction="top" offset={[0, -34]} permanent>
            New point
          </Tooltip>
        </Marker>
      )}
    </>
  );
}
