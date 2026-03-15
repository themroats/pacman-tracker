/**
 * Base Leaflet Map component with CartoDB Positron tiles and preferCanvas.
 */

import { MapContainer, TileLayer } from "react-leaflet";
import type { ReactNode } from "react";

const CARTODB_POSITRON =
  "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";
const CARTODB_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> contributors &copy; <a href="https://carto.com/">CARTO</a>';

// Default center: Seattle
const DEFAULT_CENTER: [number, number] = [47.6062, -122.3321];
const DEFAULT_ZOOM = 13;

interface MapViewProps {
  center?: [number, number];
  zoom?: number;
  children?: ReactNode;
  className?: string;
}

export default function MapView({
  center = DEFAULT_CENTER,
  zoom = DEFAULT_ZOOM,
  children,
  className = "h-full w-full",
}: MapViewProps) {
  return (
    <MapContainer
      center={center}
      zoom={zoom}
      preferCanvas={true}
      className={className}
      style={{ height: "100%", width: "100%" }}
    >
      <TileLayer url={CARTODB_POSITRON} attribution={CARTODB_ATTRIBUTION} />
      {children}
    </MapContainer>
  );
}
