/**
 * T050 — CoverageSummary
 *
 * Displays city-wide coverage percentage and per-neighborhood breakdown table.
 */

import React from "react";
import type { NeighborhoodCoverage } from "@/types/api";

interface CityData {
  id: number;
  name: string;
  coverage_percentage: number;
  streets_traveled: number;
  streets_total: number;
  distance_traveled_m: number;
  distance_total_m: number;
}

interface CoverageSummaryProps {
  city: CityData | null;
  neighborhoods: NeighborhoodCoverage[];
  onNeighborhoodClick?: (id: number) => void;
}

function formatDistance(meters: number): string {
  if (meters >= 1000) {
    return `${(meters / 1000).toFixed(1)} km`;
  }
  return `${Math.round(meters)} m`;
}

export default function CoverageSummary({
  city,
  neighborhoods,
  onNeighborhoodClick,
}: CoverageSummaryProps) {
  if (!city) {
    return (
      <div style={{ padding: "1rem" }}>
        <p style={{ color: "#6b7280" }}>Select a city to view coverage.</p>
      </div>
    );
  }

  const sorted = [...neighborhoods].sort(
    (a, b) => b.coverage_percentage - a.coverage_percentage,
  );

  return (
    <div style={{ padding: "1rem" }}>
      {/* City header */}
      <div style={{ marginBottom: "1rem" }}>
        <h2 style={{ margin: 0, fontSize: "1.25rem" }}>{city.name}</h2>
        <div
          style={{
            fontSize: "2rem",
            fontWeight: 700,
            color: city.coverage_percentage > 50 ? "#22c55e" : "#f59e0b",
          }}
        >
          {city.coverage_percentage.toFixed(1)}%
        </div>
        <p style={{ margin: 0, color: "#6b7280", fontSize: "0.875rem" }}>
          {city.streets_traveled} / {city.streets_total} streets &middot;{" "}
          {formatDistance(city.distance_traveled_m)} / {formatDistance(city.distance_total_m)}
        </p>
      </div>

      {/* Progress bar */}
      <div
        style={{
          height: "8px",
          backgroundColor: "#e5e7eb",
          borderRadius: "4px",
          marginBottom: "1rem",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${Math.min(city.coverage_percentage, 100)}%`,
            backgroundColor: "#22c55e",
            borderRadius: "4px",
            transition: "width 0.3s ease",
          }}
        />
      </div>

      {/* Neighborhood table */}
      <h3 style={{ fontSize: "1rem", marginBottom: "0.5rem" }}>Neighborhoods</h3>
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontSize: "0.8125rem",
        }}
      >
        <thead>
          <tr style={{ borderBottom: "1px solid #e5e7eb", textAlign: "left" }}>
            <th style={{ padding: "4px 8px" }}>Name</th>
            <th style={{ padding: "4px 8px", textAlign: "right" }}>Coverage</th>
            <th style={{ padding: "4px 8px", textAlign: "right" }}>Streets</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((n) => (
            <tr
              key={n.id}
              onClick={() => onNeighborhoodClick?.(n.id)}
              style={{
                borderBottom: "1px solid #f3f4f6",
                cursor: onNeighborhoodClick ? "pointer" : "default",
              }}
            >
              <td style={{ padding: "4px 8px" }}>{n.name}</td>
              <td style={{ padding: "4px 8px", textAlign: "right" }}>
                {n.coverage_percentage.toFixed(1)}%
              </td>
              <td
                style={{ padding: "4px 8px", textAlign: "right", color: "#6b7280" }}
              >
                {n.streets_traveled}/{n.streets_total}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
