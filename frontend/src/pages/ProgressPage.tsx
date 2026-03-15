/**
 * ProgressPage (T072) — progress tracking over time.
 *
 * Shows city selector, timeline chart, milestones, and overall stats.
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import TimelineChart from "@/components/ProgressTimeline/TimelineChart";
import MilestoneList from "@/components/ProgressTimeline/MilestoneList";
import StatsOverview from "@/components/ProgressTimeline/StatsOverview";
import { progressApi } from "@/api/client";
import { useCityCatalog } from "@/hooks/useCityCatalog";
import { useAppStore } from "@/store";
import type {
  OverallStatsResponse,
  Milestone,
  TimelineEntry,
} from "@/types/api";

export default function ProgressPage() {
  const isAuthenticated = useAppStore((s) => s.isAuthenticated);
  const navigate = useNavigate();
  const { cities, isBootstrapping, bootstrapError } = useCityCatalog();

  // Redirect if not authenticated
  useEffect(() => {
    if (!isAuthenticated) navigate("/");
  }, [isAuthenticated, navigate]);

  const [selectedCityId, setSelectedCityId] = useState<number | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [milestones, setMilestones] = useState<Milestone[]>([]);
  const [currentPct, setCurrentPct] = useState(0);
  const [cityName, setCityName] = useState("");
  const [stats, setStats] = useState<OverallStatsResponse | null>(null);
  const [loading, setLoading] = useState(false);

  // Load stats on mount
  useEffect(() => {
    progressApi.stats().then(setStats);
  }, []);

  // Auto-select first city
  useEffect(() => {
    const firstCity = cities[0];
    if (firstCity && selectedCityId === null) {
      setSelectedCityId(firstCity.id);
    }
  }, [cities, selectedCityId]);

  // Load city progress
  useEffect(() => {
    if (!selectedCityId) return;
    setLoading(true);
    progressApi
      .city(selectedCityId)
      .then((data) => {
        setTimeline(data.timeline);
        setMilestones(data.milestones);
        setCurrentPct(data.current_coverage_percentage);
        setCityName(data.city_name);
      })
      .finally(() => setLoading(false));
  }, [selectedCityId]);

  return (
    <div style={{ maxWidth: "900px", margin: "0 auto", padding: "2rem 1rem" }}>
      <h1 style={{ fontSize: "1.5rem", fontWeight: 700, marginBottom: "0.5rem" }}>
        Progress Timeline
      </h1>

      {/* City selector */}
      <div style={{ marginBottom: "1.5rem" }}>
        <label style={{ fontSize: "0.875rem", fontWeight: 500 }}>
          City{" "}
          <select
            value={selectedCityId ?? ""}
            disabled={isBootstrapping && cities.length === 0}
            onChange={(e) => setSelectedCityId(e.target.value ? Number(e.target.value) : null)}
            style={{
              marginLeft: "0.5rem",
              padding: "4px 8px",
              borderRadius: "6px",
              border: "1px solid #d1d5db",
            }}
          >
            <option value="">{isBootstrapping && cities.length === 0 ? "Preparing cities..." : "Select a city"}</option>
            {cities.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        {isBootstrapping && cities.length === 0 && (
          <p style={{ marginTop: "0.5rem", color: "#6b7280", fontSize: "0.8125rem" }}>
            Preparing city data for the first run. This can take a minute or two.
          </p>
        )}
        {bootstrapError && cities.length === 0 && (
          <p style={{ marginTop: "0.5rem", color: "#b91c1c", fontSize: "0.8125rem" }}>
            City bootstrap failed: {bootstrapError}
          </p>
        )}
      </div>

      {loading ? (
        <p style={{ color: "#6b7280" }}>Loading...</p>
      ) : (
        <>
          {/* Current coverage */}
          {cityName && (
            <div style={{ marginBottom: "1.5rem" }}>
              <h2 style={{ fontSize: "1.125rem", fontWeight: 600 }}>{cityName}</h2>
              <div style={{ fontSize: "2rem", fontWeight: 700, color: "#3b82f6" }}>
                {currentPct.toFixed(1)}%
              </div>
              <div
                style={{
                  width: "100%",
                  height: "8px",
                  backgroundColor: "#e5e7eb",
                  borderRadius: "4px",
                  marginTop: "0.5rem",
                }}
              >
                <div
                  style={{
                    width: `${Math.min(currentPct, 100)}%`,
                    height: "100%",
                    backgroundColor: "#3b82f6",
                    borderRadius: "4px",
                    transition: "width 0.3s ease",
                  }}
                />
              </div>
            </div>
          )}

          {/* Timeline chart */}
          <div style={{ marginBottom: "2rem" }}>
            <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "0.5rem" }}>
              Coverage Over Time
            </h3>
            <TimelineChart timeline={timeline} />
          </div>

          {/* Milestones */}
          <div style={{ marginBottom: "2rem" }}>
            <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "0.5rem" }}>
              Milestones
            </h3>
            <MilestoneList milestones={milestones} />
          </div>
        </>
      )}

      {/* Overall stats */}
      {stats && (
        <div>
          <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "0.5rem" }}>
            Overall Statistics
          </h3>
          <StatsOverview stats={stats} />
        </div>
      )}
    </div>
  );
}
