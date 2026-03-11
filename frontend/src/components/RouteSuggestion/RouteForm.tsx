/**
 * T060 — RouteForm
 *
 * Route suggestion form: starting point (map click), distance, city/neighborhood.
 */

import React, { useState } from "react";
import type { CityListItem, NeighborhoodListItem } from "@/types/api";

interface RouteFormProps {
  cities: CityListItem[];
  neighborhoods: NeighborhoodListItem[];
  onSubmit: (data: {
    start_point: { lng: number; lat: number };
    distance_meters: number;
    city_id: number;
    neighborhood_id?: number;
  }) => void;
  loading: boolean;
  /** If the user clicked the map, pre-populate the start point */
  startPoint?: { lng: number; lat: number } | null;
  /** Called when the selected city changes so the parent can load neighborhoods. */
  onCityChange?: (cityId: number | null) => void;
}

export default function RouteForm({
  cities,
  neighborhoods,
  onSubmit,
  loading,
  startPoint,
  onCityChange,
}: RouteFormProps) {
  const [distanceKm, setDistanceKm] = useState("5");
  const [cityId, setCityId] = useState<number | null>(cities[0]?.id ?? null);

  // Load neighborhoods for the initial city on mount
  React.useEffect(() => {
    if (cityId && onCityChange) {
      onCityChange(cityId);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const [neighborhoodId, setNeighborhoodId] = useState<number | null>(null);
  const [lng, setLng] = useState(startPoint?.lng?.toString() ?? "-122.32225012178574");
  const [lat, setLat] = useState(startPoint?.lat?.toString() ?? "47.623765870845304");

  // Update from map click
  React.useEffect(() => {
    if (startPoint) {
      setLng(startPoint.lng.toFixed(6));
      setLat(startPoint.lat.toFixed(6));
    }
  }, [startPoint]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!cityId) return;
    onSubmit({
      start_point: { lng: parseFloat(lng), lat: parseFloat(lat) },
      distance_meters: parseFloat(distanceKm) * 1000,
      city_id: cityId,
      neighborhood_id: neighborhoodId ?? undefined,
    });
  };

  const labelStyle: React.CSSProperties = {
    display: "flex",
    flexDirection: "column",
    gap: "4px",
    fontSize: "0.875rem",
    fontWeight: 500,
  };

  const inputStyle: React.CSSProperties = {
    padding: "6px 10px",
    borderRadius: "6px",
    border: "1px solid #d1d5db",
    fontSize: "0.875rem",
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      <label style={labelStyle}>
        Distance (km)
        <input
          aria-label="distance"
          type="number"
          min="0.5"
          max="50"
          step="0.5"
          value={distanceKm}
          onChange={(e) => setDistanceKm(e.target.value)}
          style={inputStyle}
        />
      </label>

      <div style={{ display: "flex", gap: "0.5rem" }}>
        <label style={{ ...labelStyle, flex: 1 }}>
          Longitude
          <input type="text" value={lng} onChange={(e) => setLng(e.target.value)} style={inputStyle} />
        </label>
        <label style={{ ...labelStyle, flex: 1 }}>
          Latitude
          <input type="text" value={lat} onChange={(e) => setLat(e.target.value)} style={inputStyle} />
        </label>
      </div>

      <label style={labelStyle}>
        City
        <select
          value={cityId ?? ""}
          onChange={(e) => {
            const newId = e.target.value ? Number(e.target.value) : null;
            setCityId(newId);
            setNeighborhoodId(null);
            onCityChange?.(newId);
          }}
          style={inputStyle}
        >
          {cities.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </label>

      {neighborhoods.length > 0 && (
        <label style={labelStyle}>
          Neighborhood (optional)
          <select
            value={neighborhoodId ?? ""}
            onChange={(e) => setNeighborhoodId(e.target.value ? Number(e.target.value) : null)}
            style={inputStyle}
          >
            <option value="">Any</option>
            {neighborhoods.map((n) => (
              <option key={n.id} value={n.id}>
                {n.name}
              </option>
            ))}
          </select>
        </label>
      )}

      <button
        type="submit"
        disabled={loading || !cityId}
        style={{
          padding: "10px",
          backgroundColor: loading ? "#9ca3af" : "#3b82f6",
          color: "#fff",
          border: "none",
          borderRadius: "6px",
          cursor: loading ? "not-allowed" : "pointer",
          fontWeight: 600,
          fontSize: "0.875rem",
        }}
      >
        {loading ? "Generating..." : "Suggest Route"}
      </button>
    </form>
  );
}
