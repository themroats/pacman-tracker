/**
 * NeighborhoodPlanForm — create a coverage plan for a neighborhood.
 *
 * Shown on the coverage page when a neighborhood is selected.
 */

import { useEffect, useState } from "react";
import { plansApi, startPointsApi } from "@/api/client";
import type { CoveragePlanResponse, SavedStartPoint } from "@/types/api";

interface NeighborhoodPlanFormProps {
  neighborhoodId: number;
  neighborhoodName: string;
  cityId: number;
  coveragePct: number;
  onPlanCreated: (plan: CoveragePlanResponse) => void;
}

export default function NeighborhoodPlanForm({
  neighborhoodId,
  neighborhoodName,
  cityId,
  coveragePct,
  onPlanCreated,
}: NeighborhoodPlanFormProps) {
  const [distanceKm, setDistanceKm] = useState("5");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedPoints, setSavedPoints] = useState<SavedStartPoint[]>([]);
  const [selectedPointId, setSelectedPointId] = useState<number | null>(null);

  useEffect(() => {
    if (coveragePct >= 100) return;
    startPointsApi.list().then((pts) => {
      setSavedPoints(pts);
      const def = pts.find((p) => p.is_default);
      setSelectedPointId(def?.id ?? pts[0]?.id ?? null);
    });
  }, [coveragePct]);

  const handleCreate = async () => {
    if (!selectedPointId) {
      setError("Please select a start point. Add one on the Route page first.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const plan = await plansApi.createNeighborhood({
        neighborhood_id: neighborhoodId,
        city_id: cityId,
        preferred_route_distance_m: parseFloat(distanceKm) * 1000,
        start_point_id: selectedPointId,
      });
      onPlanCreated(plan);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create plan");
    } finally {
      setLoading(false);
    }
  };

  if (coveragePct >= 100) {
    return (
      <div style={{ padding: "1rem", background: "#ecfdf5", borderRadius: "8px", border: "1px solid #6ee7b7" }}>
        <p style={{ fontWeight: 600, color: "#059669", margin: 0 }}>
          {neighborhoodName} is 100% complete!
        </p>
      </div>
    );
  }

  return (
    <div style={{ padding: "1rem", background: "#f0f9ff", borderRadius: "8px", border: "1px solid #93c5fd" }}>
      <h3 style={{ margin: "0 0 0.5rem", fontSize: "0.9375rem", fontWeight: 600 }}>
        Complete {neighborhoodName}
      </h3>
      <p style={{ fontSize: "0.8125rem", color: "#6b7280", margin: "0 0 0.75rem" }}>
        Currently {coveragePct.toFixed(1)}% covered. Generate a plan to cover all remaining streets.
      </p>

      <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.875rem", fontWeight: 500, marginBottom: "0.75rem" }}>
        Start / finish point
        {savedPoints.length === 0 ? (
          <p style={{ fontSize: "0.8125rem", color: "#b91c1c", margin: "4px 0 0" }}>
            No saved start points. Add one on the Route page first.
          </p>
        ) : (
          <select
            value={selectedPointId ?? ""}
            onChange={(e) => setSelectedPointId(Number(e.target.value))}
            style={{ padding: "6px 10px", borderRadius: "6px", border: "1px solid #d1d5db", fontSize: "0.875rem" }}
          >
            {savedPoints.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}{p.is_default ? " (default)" : ""}
              </option>
            ))}
          </select>
        )}
      </label>

      <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.875rem", fontWeight: 500, marginBottom: "0.75rem" }}>
        Preferred distance per route (km)
        <input
          type="number"
          min="1"
          max="20"
          step="0.5"
          value={distanceKm}
          onChange={(e) => setDistanceKm(e.target.value)}
          style={{ padding: "6px 10px", borderRadius: "6px", border: "1px solid #d1d5db", fontSize: "0.875rem" }}
        />
      </label>

      {error && (
        <p style={{ color: "#dc2626", fontSize: "0.8rem", margin: "0 0 0.5rem" }}>{error}</p>
      )}

      <button
        onClick={handleCreate}
        disabled={loading || !selectedPointId}
        style={{
          padding: "8px 16px",
          backgroundColor: loading || !selectedPointId ? "#9ca3af" : "#8b5cf6",
          color: "#fff",
          border: "none",
          borderRadius: "6px",
          cursor: loading || !selectedPointId ? "not-allowed" : "pointer",
          fontWeight: 600,
          fontSize: "0.875rem",
        }}
      >
        {loading ? "Generating plan..." : "Generate Coverage Plan"}
      </button>
    </div>
  );
}
