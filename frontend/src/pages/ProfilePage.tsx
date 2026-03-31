/**
 * ProfilePage — dashboard of collapsible summary cards:
 *
 * 1. Activities — stats + paginated activity list
 * 2. Progress  — city coverage timeline + milestones
 * 3. Plans & Routes — coverage plans, goals, route suggestions
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import TimelineChart from "@/components/ProgressTimeline/TimelineChart";
import MilestoneList from "@/components/ProgressTimeline/MilestoneList";
import StatsOverview from "@/components/ProgressTimeline/StatsOverview";
import ActivityList from "@/components/Profile/ActivityList";
import ProfileCard from "@/components/Profile/ProfileCard";
import PlanHistory from "@/components/Profile/PlanHistory";
import GoalHistory from "@/components/Profile/GoalHistory";
import RouteHistory from "@/components/Profile/RouteHistory";
import { progressApi, plansApi, goalsApi, routesApi } from "@/api/client";
import { useCityCatalog } from "@/hooks/useCityCatalog";
import { useAppStore } from "@/store";
import { useIsMobile } from "@/hooks/useIsMobile";
import type {
  OverallStatsResponse,
  Milestone,
  TimelineEntry,
} from "@/types/api";

function formatNumber(n: number): string {
  return n.toLocaleString("en-US");
}

export default function ProfilePage() {
  const isAuthenticated = useAppStore((s) => s.isAuthenticated);
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const { cities, isBootstrapping, bootstrapError } = useCityCatalog();

  useEffect(() => {
    if (!isAuthenticated) navigate("/");
  }, [isAuthenticated, navigate]);

  // --- Stats ---
  const [stats, setStats] = useState<OverallStatsResponse | null>(null);

  // --- Progress state ---
  const [selectedCityId, setSelectedCityId] = useState<number | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [milestones, setMilestones] = useState<Milestone[]>([]);
  const [currentPct, setCurrentPct] = useState(0);
  const [cityName, setCityName] = useState("");
  const [progressLoading, setProgressLoading] = useState(false);

  // --- Plans counts for summary ---
  const [planCount, setPlanCount] = useState<number | null>(null);
  const [goalCount, setGoalCount] = useState<number | null>(null);
  const [routeCount, setRouteCount] = useState<number | null>(null);

  // Load summary data on mount
  useEffect(() => {
    progressApi.stats().then(setStats).catch((e) => console.warn("Failed to load stats", e));
    plansApi.list().then((p) => setPlanCount(p.filter((x) => x.goal_id === null).length)).catch((e) => console.warn("Failed to load plans", e));
    goalsApi.list().then((g) => setGoalCount(g.length)).catch((e) => console.warn("Failed to load goals", e));
    routesApi.history().then((r) => setRouteCount(r.routes.length)).catch((e) => console.warn("Failed to load routes", e));
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
    setProgressLoading(true);
    progressApi
      .city(selectedCityId)
      .then((data) => {
        setTimeline(data.timeline);
        setMilestones(data.milestones);
        setCurrentPct(data.current_coverage_percentage);
        setCityName(data.city_name);
      })
      .catch(() => {
        setTimeline([]);
        setMilestones([]);
        setCurrentPct(0);
        setCityName("");
      })
      .finally(() => setProgressLoading(false));
  }, [selectedCityId]);

  // --- Build summary strings ---
  const activitySummary = stats
    ? `${formatNumber(stats.total_activities)} activities — ${formatNumber(Math.round(stats.total_distance_meters / 1000))} km — ${formatNumber(stats.total_unique_streets)} streets`
    : "Loading...";

  const progressSummary = cityName
    ? `${cityName}: ${currentPct.toFixed(1)}% coverage`
    : "Select a city to view progress";

  const plansSummary = [
    goalCount !== null ? `${goalCount} goal${goalCount !== 1 ? "s" : ""}` : null,
    planCount !== null ? `${planCount} plan${planCount !== 1 ? "s" : ""}` : null,
    routeCount !== null ? `${routeCount} route${routeCount !== 1 ? "s" : ""}` : null,
  ]
    .filter(Boolean)
    .join(" · ") || "Loading...";

  return (
    <div style={{ maxWidth: "900px", margin: "0 auto", padding: isMobile ? "1rem 0.75rem" : "2rem 1rem" }}>
      <h1 style={{ fontSize: "1.5rem", fontWeight: 700, marginBottom: "1rem" }}>
        Profile
      </h1>

      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        {/* ---- Activities Card ---- */}
        <ProfileCard title="Activities" summary={activitySummary} defaultOpen={false}>
          {stats && (
            <div style={{ marginBottom: "1.5rem" }}>
              <StatsOverview stats={stats} />
            </div>
          )}
          <ActivityList />
        </ProfileCard>

        {/* ---- Progress Card ---- */}
        <ProfileCard title="Progress" summary={progressSummary} defaultOpen={false}>
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
                <option value="">
                  {isBootstrapping && cities.length === 0 ? "Preparing cities..." : "Select a city"}
                </option>
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

          {progressLoading ? (
            <p style={{ color: "#6b7280" }}>Loading...</p>
          ) : (
            <>
              {cityName && (
                <div style={{ marginBottom: "1.5rem" }}>
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

              {timeline.length > 0 && (
                <div style={{ marginBottom: "2rem" }}>
                  <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "0.5rem" }}>
                    Coverage Over Time
                  </h3>
                  <TimelineChart timeline={timeline} />
                </div>
              )}

              {milestones.length > 0 && (
                <div style={{ marginBottom: "1rem" }}>
                  <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "0.5rem" }}>
                    Milestones
                  </h3>
                  <MilestoneList milestones={milestones} />
                </div>
              )}

              {cityName && timeline.length === 0 && milestones.length === 0 && (
                <p style={{ color: "#6b7280", fontSize: "0.875rem" }}>
                  No progress data yet for {cityName}. Run coverage matching from the Coverage page to generate snapshots.
                </p>
              )}
            </>
          )}
        </ProfileCard>

        {/* ---- Plans & Routes Card ---- */}
        <ProfileCard title="Plans & Routes" summary={plansSummary} defaultOpen={false}>
          <div style={{ marginBottom: "1.5rem" }}>
            <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "0.5rem" }}>
              Coverage Goals
            </h3>
            <GoalHistory />
          </div>

          <div style={{ marginBottom: "1.5rem" }}>
            <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "0.5rem" }}>
              Neighborhood Plans
            </h3>
            <PlanHistory />
          </div>

          <div>
            <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "0.5rem" }}>
              Route Suggestions
            </h3>
            <RouteHistory />
          </div>
        </ProfileCard>
      </div>
    </div>
  );
}
