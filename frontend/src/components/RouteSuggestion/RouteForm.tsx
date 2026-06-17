/**
 * RouteForm
 *
 * Route suggestion form: starting point (map click or saved), distance,
 * city/neighborhood, variation slider, and route preferences.
 */

import React, { useState } from "react";
import type { CityListItem, NeighborhoodListItem, RoutePreferences, SavedStartPoint } from "@/types/api";
import { startPointsApi } from "@/api/client";
import { useIsMobile } from "@/hooks/useIsMobile";

interface RouteFormProps {
  cities: CityListItem[];
  neighborhoods: NeighborhoodListItem[];
  onSubmit: (data: {
    start_point: { lng: number; lat: number };
    distance_meters: number;
    city_id: number;
    neighborhood_id?: number;
    variation?: number;
    preferences?: RoutePreferences;
  }) => void;
  loading: boolean;
  /** If the user clicked/dragged the map, pre-populate the start point */
  startPoint?: { lng: number; lat: number } | null;
  /** Called when the selected city changes so the parent can load neighborhoods. */
  onCityChange?: (cityId: number | null) => void;
  citiesLoading?: boolean;
  /** Saved start points (owned by parent for map sharing). */
  savedPoints: SavedStartPoint[];
  /** Currently selected saved point ID. */
  selectedPointId: number | null;
  /** Called when user selects a saved point from dropdown. */
  onSelectSavedPoint: (id: number | null) => void;
  /** Called when saved points list changes (create/delete). */
  onSavedPointsChange: (points: SavedStartPoint[]) => void;
  /** Whether we're in "add new point" mode (shows pin on map). */
  addingPoint: boolean;
  /** Toggle add-point mode. */
  onAddingPointChange: (adding: boolean) => void;
}

const DEFAULT_PREFERENCES: RoutePreferences = {
  residential: 1.0,
  main_roads: 0.5,
  trails: 1.0,
  other: 0.7,
};

export default function RouteForm({
  cities,
  neighborhoods,
  onSubmit,
  loading,
  startPoint,
  onCityChange,
  citiesLoading = false,
  savedPoints,
  selectedPointId,
  onSelectSavedPoint,
  onSavedPointsChange,
  addingPoint,
  onAddingPointChange,
}: RouteFormProps) {
  const [distanceKm, setDistanceKm] = useState("5");
  const [cityId, setCityId] = useState<number | null>(cities[0]?.id ?? null);

  // Load neighborhoods when city changes
  React.useEffect(() => {
    if (cityId && onCityChange) {
      onCityChange(cityId);
    }
  }, [cityId, onCityChange]);
  const [neighborhoodId, setNeighborhoodId] = useState<number | null>(null);
  const [lng, setLng] = useState(startPoint?.lng?.toString() ?? "-122.32225012178574");
  const [lat, setLat] = useState(startPoint?.lat?.toString() ?? "47.623765870845304");

  // Variation & preferences
  const [variation, setVariation] = useState(0.5);
  const [showPrefs, setShowPrefs] = useState(false);
  const [preferences, setPreferences] = useState<RoutePreferences>({ ...DEFAULT_PREFERENCES });

  // Add-point mode: shows lat/lng + name fields
  const [savingPoint, setSavingPoint] = useState(false);
  const [savePointName, setSavePointName] = useState("");

  // Update from map click / drag
  React.useEffect(() => {
    if (startPoint) {
      setLng(startPoint.lng.toFixed(6));
      setLat(startPoint.lat.toFixed(6));
    }
  }, [startPoint]);

  const [validationError, setValidationError] = useState<string | null>(null);
  const isMobile = useIsMobile();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!cityId) return;
    if (!selectedPointId) {
      setValidationError("Select a start point or add a new one");
      return;
    }

    const selected = savedPoints.find((p) => p.id === selectedPointId);
    if (!selected) return;

    const parsedDist = parseFloat(distanceKm);
    if (isNaN(parsedDist) || parsedDist <= 0 || parsedDist > 50) {
      setValidationError("Distance must be between 0.5 and 50 km");
      return;
    }

    setValidationError(null);
    onSubmit({
      start_point: { lng: selected.lng, lat: selected.lat },
      distance_meters: parsedDist * 1000,
      city_id: cityId,
      neighborhood_id: neighborhoodId ?? undefined,
      variation,
      preferences,
    });
  };

  const handleSavePoint = async () => {
    if (!savePointName.trim()) return;
    const parsedLng = parseFloat(lng);
    const parsedLat = parseFloat(lat);
    if (isNaN(parsedLng) || parsedLng < -180 || parsedLng > 180) {
      setValidationError("Longitude must be between -180 and 180");
      return;
    }
    if (isNaN(parsedLat) || parsedLat < -90 || parsedLat > 90) {
      setValidationError("Latitude must be between -90 and 90");
      return;
    }
    setSavingPoint(true);
    setValidationError(null);
    try {
      const pt = await startPointsApi.create({
        name: savePointName.trim(),
        lng: parsedLng,
        lat: parsedLat,
        is_default: savedPoints.length === 0,
      });
      onSavedPointsChange([...savedPoints, pt]);
      onSelectSavedPoint(pt.id);
      onAddingPointChange(false);
      setSavePointName("");
    } catch (err) {
      console.error("Failed to save start point:", err);
    } finally {
      setSavingPoint(false);
    }
  };

  const handleSelectSavedPoint = (id: number | null) => {
    onSelectSavedPoint(id);
  };

  const handleDeleteSavedPoint = async (id: number) => {
    try {
      await startPointsApi.remove(id);
      onSavedPointsChange(savedPoints.filter((p) => p.id !== id));
      if (selectedPointId === id) onSelectSavedPoint(null);
    } catch (err) {
      console.error("Failed to delete start point:", err);
    }
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

  const smallBtnStyle: React.CSSProperties = {
    padding: "4px 8px",
    fontSize: "0.75rem",
    borderRadius: "4px",
    border: "1px solid #d1d5db",
    background: "#f9fafb",
    cursor: "pointer",
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

      {/* Start point section */}
      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        <span style={{ fontSize: "0.875rem", fontWeight: 500 }}>Start from</span>

        {savedPoints.length > 0 && (
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <select
              value={selectedPointId ?? ""}
              onChange={(e) => handleSelectSavedPoint(e.target.value ? Number(e.target.value) : null)}
              style={{ ...inputStyle, flex: 1 }}
            >
              <option value="">Select a saved point</option>
              {savedPoints.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}{p.is_default ? " ★" : ""}
                </option>
              ))}
            </select>
            {selectedPointId && (
              <button type="button" onClick={() => handleDeleteSavedPoint(selectedPointId)} style={smallBtnStyle}>
                ✕
              </button>
            )}
          </div>
        )}

        {savedPoints.length === 0 && !addingPoint && (
          <p style={{ fontSize: "0.8125rem", color: "#6b7280", margin: 0 }}>
            No saved points yet. Add one to get started.
          </p>
        )}

        {!addingPoint ? (
          <button type="button" onClick={() => onAddingPointChange(true)} style={{ ...smallBtnStyle, alignSelf: "flex-start" }}>
            + Add start point
          </button>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", padding: "0.5rem", background: "#f9fafb", borderRadius: "6px", border: "1px solid #e5e7eb" }}>
            <span style={{ fontSize: "0.8125rem", fontWeight: 500 }}>New start point</span>
            <p style={{ fontSize: "0.75rem", color: "#6b7280", margin: 0 }}>
              Click or drag the pin on the map to set the location.
            </p>
            <div style={{ display: "flex", gap: "0.5rem", flexDirection: isMobile ? "column" : "row" }}>
              <label style={{ ...labelStyle, flex: 1 }}>
                Longitude
                <input type="text" value={lng} onChange={(e) => setLng(e.target.value)} style={inputStyle} />
              </label>
              <label style={{ ...labelStyle, flex: 1 }}>
                Latitude
                <input type="text" value={lat} onChange={(e) => setLat(e.target.value)} style={inputStyle} />
              </label>
            </div>
            <input
              type="text"
              placeholder="Name (e.g. Home, Office)"
              value={savePointName}
              onChange={(e) => setSavePointName(e.target.value)}
              style={inputStyle}
              maxLength={100}
            />
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button type="button" onClick={handleSavePoint} disabled={savingPoint || !savePointName.trim()} style={{
                ...smallBtnStyle,
                background: savePointName.trim() ? "#3b82f6" : "#f9fafb",
                color: savePointName.trim() ? "#fff" : undefined,
                border: savePointName.trim() ? "1px solid #3b82f6" : undefined,
              }}>
                {savingPoint ? "Saving..." : "Save point"}
              </button>
              <button type="button" onClick={() => { onAddingPointChange(false); setSavePointName(""); setValidationError(null); }} style={smallBtnStyle}>
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>

      <label style={labelStyle}>
        City
        <select
          value={cityId ?? ""}
          disabled={citiesLoading && cities.length === 0}
          onChange={(e) => {
            const newId = e.target.value ? Number(e.target.value) : null;
            setCityId(newId);
            setNeighborhoodId(null);
            onCityChange?.(newId);
          }}
          style={inputStyle}
        >
          <option value="">{citiesLoading && cities.length === 0 ? "Preparing cities..." : "Select a city"}</option>
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

      {/* Variation slider */}
      <label style={labelStyle}>
        Route variety
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <span style={{ fontSize: "0.75rem", color: "#6b7280" }}>Efficient</span>
          <input
            type="range"
            min="0"
            max="1"
            step="0.1"
            value={variation}
            onChange={(e) => setVariation(parseFloat(e.target.value))}
            style={{ flex: 1 }}
          />
          <span style={{ fontSize: "0.75rem", color: "#6b7280" }}>Surprise me</span>
        </div>
      </label>

      {/* Preferences toggle */}
      <button
        type="button"
        onClick={() => setShowPrefs(!showPrefs)}
        style={{
          ...smallBtnStyle,
          alignSelf: "flex-start",
          display: "flex",
          alignItems: "center",
          gap: "4px",
        }}
      >
        {showPrefs ? "▼" : "▶"} Street preferences
      </button>

      {showPrefs && (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", padding: "0.5rem", background: "#f9fafb", borderRadius: "6px" }}>
          {(Object.entries(preferences) as [keyof RoutePreferences, number][]).map(([key, value]) => (
            <label key={key} style={{ ...labelStyle, flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{ textTransform: "capitalize" }}>{key.replace("_", " ")}</span>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", width: "60%" }}>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={value}
                  onChange={(e) =>
                    setPreferences((prev) => ({ ...prev, [key]: parseFloat(e.target.value) }))
                  }
                  style={{ flex: 1 }}
                />
                <span style={{ fontSize: "0.75rem", width: "2rem", textAlign: "right" }}>
                  {value === 0 ? "Avoid" : value < 0.5 ? "Low" : value < 1 ? "Med" : "High"}
                </span>
              </div>
            </label>
          ))}
        </div>
      )}

      {validationError && (
        <p role="alert" style={{ color: "#dc2626", fontSize: "0.8rem", margin: 0 }}>
          {validationError}
        </p>
      )}

      <button
        type="submit"
        disabled={loading || !cityId || !selectedPointId || (citiesLoading && cities.length === 0)}
        style={{
          padding: "10px",
          backgroundColor: loading || !selectedPointId ? "#9ca3af" : "#3b82f6",
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
