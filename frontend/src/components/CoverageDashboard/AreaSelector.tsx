/**
 * T051 — AreaSelector
 *
 * City / neighborhood selector component — top-level dropdown controls.
 */

import React from "react";
import type { CityListItem, NeighborhoodListItem } from "@/types/api";

interface AreaSelectorProps {
  cities: CityListItem[];
  neighborhoods: NeighborhoodListItem[];
  selectedCityId: number | null;
  selectedNeighborhoodId: number | null;
  onCityChange: (cityId: number | null) => void;
  onNeighborhoodChange: (neighborhoodId: number | null) => void;
}

export default function AreaSelector({
  cities,
  neighborhoods,
  selectedCityId,
  selectedNeighborhoodId,
  onCityChange,
  onNeighborhoodChange,
}: AreaSelectorProps) {
  const selectStyle: React.CSSProperties = {
    padding: "6px 10px",
    borderRadius: "6px",
    border: "1px solid #d1d5db",
    fontSize: "0.875rem",
    minWidth: "160px",
    backgroundColor: "#fff",
  };

  return (
    <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
      {/* City selector */}
      <label style={{ fontSize: "0.875rem", fontWeight: 500 }}>
        City
        <select
          role="combobox"
          value={selectedCityId ?? ""}
          onChange={(e) => {
            const val = e.target.value;
            onCityChange(val ? Number(val) : null);
            onNeighborhoodChange(null);
          }}
          style={{ ...selectStyle, marginLeft: "6px" }}
        >
          <option value="">Select a city</option>
          {cities.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}, {c.state}
            </option>
          ))}
        </select>
      </label>

      {/* Neighborhood selector – only shown when a city is selected */}
      {selectedCityId && neighborhoods.length > 0 && (
        <label style={{ fontSize: "0.875rem", fontWeight: 500 }}>
          Neighborhood
          <select
            value={selectedNeighborhoodId ?? ""}
            onChange={(e) => {
              const val = e.target.value;
              onNeighborhoodChange(val ? Number(val) : null);
            }}
            style={{ ...selectStyle, marginLeft: "6px" }}
          >
            <option value="">All neighborhoods</option>
            {neighborhoods.map((n) => (
              <option key={n.id} value={n.id}>
                {n.name} ({n.coverage_percentage.toFixed(1)}%)
              </option>
            ))}
          </select>
        </label>
      )}
    </div>
  );
}
