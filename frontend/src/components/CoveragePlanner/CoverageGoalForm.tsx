/**
 * CoverageGoalForm — create a city-level coverage goal.
 */

import { useState } from "react";
import { goalsApi } from "@/api/client";
import type { CoverageGoalResponse } from "@/types/api";

interface CoverageGoalFormProps {
  cityId: number;
  cityName: string;
  currentCoveragePct: number;
  onGoalCreated: (goal: CoverageGoalResponse) => void;
}

export default function CoverageGoalForm({
  cityId,
  cityName,
  currentCoveragePct,
  onGoalCreated,
}: CoverageGoalFormProps) {
  const [targetPct, setTargetPct] = useState(
    Math.min(currentCoveragePct + 10, 100).toFixed(0),
  );
  const [distanceKm, setDistanceKm] = useState("5");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreate = async () => {
    const target = parseFloat(targetPct);
    if (isNaN(target) || target <= currentCoveragePct || target > 100) {
      setError(`Target must be between ${currentCoveragePct.toFixed(1)}% and 100%`);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const goal = await goalsApi.create({
        city_id: cityId,
        target_coverage_pct: target,
        preferred_route_distance_m: parseFloat(distanceKm) * 1000,
      });
      onGoalCreated(goal);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create goal");
    } finally {
      setLoading(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    padding: "6px 10px",
    borderRadius: "6px",
    border: "1px solid #d1d5db",
    fontSize: "0.875rem",
  };

  return (
    <div style={{ padding: "1rem", background: "#faf5ff", borderRadius: "8px", border: "1px solid #c4b5fd" }}>
      <h3 style={{ margin: "0 0 0.5rem", fontSize: "0.9375rem", fontWeight: 600 }}>
        Coverage Goal for {cityName}
      </h3>
      <p style={{ fontSize: "0.8125rem", color: "#6b7280", margin: "0 0 0.75rem" }}>
        Currently at {currentCoveragePct.toFixed(1)}%. Set a target and we'll find the optimal
        neighborhoods to reach it.
      </p>

      <div style={{ display: "flex", gap: "0.75rem", marginBottom: "0.75rem" }}>
        <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.875rem", fontWeight: 500, flex: 1 }}>
          Target coverage (%)
          <input
            type="number"
            min={Math.ceil(currentCoveragePct + 1)}
            max="100"
            value={targetPct}
            onChange={(e) => setTargetPct(e.target.value)}
            style={inputStyle}
          />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.875rem", fontWeight: 500, flex: 1 }}>
          Route distance (km)
          <input
            type="number"
            min="1"
            max="20"
            step="0.5"
            value={distanceKm}
            onChange={(e) => setDistanceKm(e.target.value)}
            style={inputStyle}
          />
        </label>
      </div>

      {error && (
        <p style={{ color: "#dc2626", fontSize: "0.8rem", margin: "0 0 0.5rem" }}>{error}</p>
      )}

      <button
        onClick={handleCreate}
        disabled={loading}
        style={{
          padding: "8px 16px",
          backgroundColor: loading ? "#9ca3af" : "#7c3aed",
          color: "#fff",
          border: "none",
          borderRadius: "6px",
          cursor: loading ? "not-allowed" : "pointer",
          fontWeight: 600,
          fontSize: "0.875rem",
        }}
      >
        {loading ? "Analyzing..." : "Find Optimal Plan"}
      </button>
    </div>
  );
}
