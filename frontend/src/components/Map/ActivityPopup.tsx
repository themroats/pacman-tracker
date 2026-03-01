/**
 * ActivityPopup — detail popup for clicked activities.
 */

import { Popup } from "react-leaflet";
import type { ActivityDetail } from "@/types/api";

interface ActivityPopupProps {
  activity: ActivityDetail | null;
  position: [number, number] | null;
  onClose: () => void;
}

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m ${s}s`;
}

function formatDistance(meters: number): string {
  if (meters >= 1000) return `${(meters / 1000).toFixed(2)} km`;
  return `${Math.round(meters)} m`;
}

function formatPace(paceMinPerKm: number | null | undefined): string {
  if (!paceMinPerKm) return "—";
  const minutes = Math.floor(paceMinPerKm);
  const seconds = Math.round((paceMinPerKm - minutes) * 60);
  return `${minutes}:${String(seconds).padStart(2, "0")} /km`;
}

export default function ActivityPopup({ activity, position, onClose }: ActivityPopupProps) {
  if (!activity || !position) return null;

  return (
    <Popup position={position} onClose={onClose}>
      <div style={{ minWidth: 200 }}>
        <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "1rem" }}>{activity.name}</h3>
        <p style={{ margin: "0.25rem 0", color: "#666", fontSize: "0.85rem" }}>
          {activity.sport_type} • {new Date(activity.start_date).toLocaleDateString()}
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.25rem", fontSize: "0.85rem" }}>
          <span>Distance:</span>
          <span>{formatDistance(activity.distance_meters)}</span>
          <span>Duration:</span>
          <span>{formatDuration(activity.duration_seconds)}</span>
          <span>Pace:</span>
          <span>{formatPace(activity.pace_min_per_km)}</span>
        </div>
      </div>
    </Popup>
  );
}
