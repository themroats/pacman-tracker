/**
 * ProgressPage (T072) — progress tracking over time.
 *
 * Shows city selector, timeline chart, milestones, and overall stats.
 */

import React, { useCallback, useEffect, useState } from "react";
import TimelineChart from "@/components/ProgressTimeline/TimelineChart";
import MilestoneList from "@/components/ProgressTimeline/MilestoneList";
import StatsOverview from "@/components/ProgressTimeline/StatsOverview";
import { progressApi, citiesApi } from "@/api/client";
import { useAppStore } from "@/store";
import type {
  ProgressResponse,
  OverallStatsResponse,
  Milestone,
  TimelineEntry,
} from "@/types/api";

export default function ProgressPage() {
  const cities = useAppStore((s) => s.cities);
  const setCities = useAppStore((s) => s.setCities);

  const [selectedCityId, setSelectedCityId] = useState<number | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [milestones, setMilestones] = useState<Milestone[]>([]);
  const [currentPct, setCurrentPct] = useState(0);
  const [cityName, setCityName] = useState("");
  const [stats, setStats] = useState<OverallStatsResponse | null>(null);
  const [loading, setLoading] = useState(false);

  // Load cities on mount
  useEffect(() => {
    if (cities.length === 0) {
      citiesApi.list().then((r) => setCities(r.cities)).catch(() => {});
    }
  }, [cities.length, setCities]);

  // Load stats on mount
  useEffect(() => {
    progressApi.stats().then(setStats).catch(() => {});
  }, []);

  // Auto-select first city
  useEffect(() => {
    if (cities.length > 0 && selectedCityId === null) {
      setSelectedCityId(cities[0].id);
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
      .catch(() => {})
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
            onChange={(e) => setSelectedCityId(e.target.value ? Number(e.target.value) : null)}
            style={{
              marginLeft: "0.5rem",
              padding: "4px 8px",
              borderRadius: "6px",
              border: "1px solid #d1d5db",
            }}
          >
            {cities.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
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
