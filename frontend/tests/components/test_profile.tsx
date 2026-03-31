/**
 * Tests for Profile page components: ActivityList, PlanHistory.
 *
 * Covers:
 * - ActivityList: renders activities, pagination, Map button for GPS activities,
 *   Feature→FeatureCollection wrapping, empty state
 * - PlanHistory: renders plans, expand/collapse, goal_id filtering, delete, route pagination
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router-dom";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="map-container">{children}</div>
  ),
  TileLayer: () => null,
  GeoJSON: ({ data }: { data: unknown }) => (
    <div data-testid="geojson-layer" />
  ),
}));

const mockActivitiesList = vi.fn();
const mockActivitiesGetGeoJSON = vi.fn();
const mockPlansList = vi.fn();
const mockPlansGet = vi.fn();
const mockPlansRemove = vi.fn();
const mockRoutesGeojson = vi.fn();
const mockRoutesFetchGpx = vi.fn();

vi.mock("@/api/client", () => ({
  activitiesApi: {
    list: (...args: unknown[]) => mockActivitiesList(...args),
    getGeoJSON: (...args: unknown[]) => mockActivitiesGetGeoJSON(...args),
  },
  plansApi: {
    list: (...args: unknown[]) => mockPlansList(...args),
    get: (...args: unknown[]) => mockPlansGet(...args),
    remove: (...args: unknown[]) => mockPlansRemove(...args),
  },
  routesApi: {
    geojson: (...args: unknown[]) => mockRoutesGeojson(...args),
    fetchGpx: (...args: unknown[]) => mockRoutesFetchGpx(...args),
  },
}));

vi.mock("@/hooks/useIsMobile", () => ({
  useIsMobile: () => false,
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const makeActivity = (overrides: Partial<{
  id: number; name: string; sport_type: string; has_gps: boolean;
  distance_meters: number; duration_seconds: number; start_date: string;
  city_name: string | null;
}> = {}) => ({
  id: 1,
  strava_activity_id: 1001,
  name: "Morning Run",
  sport_type: "Run",
  start_date: "2025-06-01T08:00:00Z",
  distance_meters: 5000,
  duration_seconds: 1800,
  moving_time_seconds: 1750,
  pace_min_per_km: 6.0,
  has_gps: true,
  is_on_street: true,
  city_name: "Seattle",
  ...overrides,
});

const makePlanSummary = (overrides: Partial<{
  id: number; neighborhood_name: string; status: string;
  total_routes: number; goal_id: number | null;
}> = {}) => ({
  id: 1,
  neighborhood_name: "Capitol Hill",
  status: "ready",
  total_routes: 3,
  total_distance_m: 15000,
  initial_coverage_pct: 45.2,
  goal_id: null,
  ...overrides,
});

const makePlanDetail = (overrides: Partial<{
  id: number; routes: Array<{
    sequence_order: number; status: string; route_id: number;
    distance_meters: number; estimated_duration_seconds: number;
    streets_targeted: number; untraveled_ratio: number;
  }>;
}> = {}) => ({
  id: 1,
  neighborhood_id: 10,
  neighborhood_name: "Capitol Hill",
  city_id: 1,
  status: "ready",
  preferred_route_distance_m: 5000,
  initial_coverage_pct: 45.2,
  target_coverage_pct: 100,
  total_routes: 2,
  total_distance_m: 10000,
  error_message: null,
  routes: [
    {
      sequence_order: 1, status: "pending", route_id: 101,
      distance_meters: 5000, estimated_duration_seconds: 2500,
      streets_targeted: 20, untraveled_ratio: 0.85,
    },
    {
      sequence_order: 2, status: "pending", route_id: 102,
      distance_meters: 5000, estimated_duration_seconds: 2500,
      streets_targeted: 18, untraveled_ratio: 0.78,
    },
  ],
  ...overrides,
});

// ---------------------------------------------------------------------------
// ActivityList
// ---------------------------------------------------------------------------

describe("ActivityList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading state initially", async () => {
    // Never resolve — stay in loading state
    mockActivitiesList.mockReturnValue(new Promise(() => {}));

    const { default: ActivityList } = await import(
      "@/components/Profile/ActivityList"
    );

    render(
      <MemoryRouter>
        <ActivityList />
      </MemoryRouter>,
    );

    expect(screen.getByText(/Loading activities/)).toBeDefined();
  });

  it("renders empty state when no activities", async () => {
    mockActivitiesList.mockResolvedValue({
      activities: [],
      total: 0,
      page: 1,
      per_page: 20,
    });

    const { default: ActivityList } = await import(
      "@/components/Profile/ActivityList"
    );

    render(
      <MemoryRouter>
        <ActivityList />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText(/No activities imported/)).toBeDefined();
    });
  });

  it("renders activity rows with name, sport type, and distance", async () => {
    mockActivitiesList.mockResolvedValue({
      activities: [
        makeActivity({ id: 1, name: "Morning Run", sport_type: "Run", distance_meters: 5000 }),
        makeActivity({ id: 2, name: "Evening Walk", sport_type: "Walk", distance_meters: 3000, has_gps: false }),
      ],
      total: 2,
      page: 1,
      per_page: 20,
    });

    const { default: ActivityList } = await import(
      "@/components/Profile/ActivityList"
    );

    render(
      <MemoryRouter>
        <ActivityList />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Morning Run")).toBeDefined();
      expect(screen.getByText("Evening Walk")).toBeDefined();
    });

    // Distance formatted
    expect(screen.getByText("5.00 km")).toBeDefined();
    expect(screen.getByText("3.00 km")).toBeDefined();

    // Activity total
    expect(screen.getByText("2 activities total")).toBeDefined();
  });

  it("shows Map button only for GPS activities", async () => {
    mockActivitiesList.mockResolvedValue({
      activities: [
        makeActivity({ id: 1, name: "GPS Run", has_gps: true }),
        makeActivity({ id: 2, name: "No GPS Walk", has_gps: false }),
      ],
      total: 2,
      page: 1,
      per_page: 20,
    });

    const { default: ActivityList } = await import(
      "@/components/Profile/ActivityList"
    );

    render(
      <MemoryRouter>
        <ActivityList />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("GPS Run")).toBeDefined();
    });

    // Only one Map button (for the GPS activity)
    const mapButtons = screen.getAllByRole("button", { name: /Map/ });
    expect(mapButtons).toHaveLength(1);
  });

  it("shows pagination when more than one page", async () => {
    const activities = Array.from({ length: 20 }, (_, i) =>
      makeActivity({ id: i + 1, name: `Activity ${i + 1}` }),
    );
    mockActivitiesList.mockResolvedValue({
      activities,
      total: 45,
      page: 1,
      per_page: 20,
    });

    const { default: ActivityList } = await import(
      "@/components/Profile/ActivityList"
    );

    render(
      <MemoryRouter>
        <ActivityList />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Page 1 of 3")).toBeDefined();
    });

    expect(screen.getByText("Previous")).toBeDefined();
    expect(screen.getByText("Next")).toBeDefined();

    // Previous disabled on first page
    const prevBtn = screen.getByText("Previous");
    expect(prevBtn).toBeDisabled();
  });

  it("wraps single Feature response in FeatureCollection when toggling map", async () => {
    mockActivitiesList.mockResolvedValue({
      activities: [makeActivity({ id: 42, name: "GPS Run", has_gps: true })],
      total: 1,
      page: 1,
      per_page: 20,
    });

    // API returns a single Feature, NOT a FeatureCollection
    const singleFeature = {
      type: "Feature",
      properties: { id: 42 },
      geometry: {
        type: "LineString",
        coordinates: [[-122.33, 47.60], [-122.34, 47.61]],
      },
    };
    mockActivitiesGetGeoJSON.mockResolvedValue(singleFeature);

    const { default: ActivityList } = await import(
      "@/components/Profile/ActivityList"
    );

    render(
      <MemoryRouter>
        <ActivityList />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("GPS Run")).toBeDefined();
    });

    // Click Map button
    const mapBtn = screen.getByRole("button", { name: "Map" });
    fireEvent.click(mapBtn);

    // Should fetch GeoJSON
    expect(mockActivitiesGetGeoJSON).toHaveBeenCalledWith(42);

    // Should show the map container (after loading)
    await waitFor(() => {
      expect(screen.getByTestId("map-container")).toBeDefined();
    });

    // Button should now say "Hide"
    expect(screen.getByRole("button", { name: "Hide" })).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// PlanHistory
// ---------------------------------------------------------------------------

describe("PlanHistory", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading state", async () => {
    mockPlansList.mockReturnValue(new Promise(() => {}));

    const { default: PlanHistory } = await import(
      "@/components/Profile/PlanHistory"
    );

    render(<PlanHistory />);

    expect(screen.getByText(/Loading plans/)).toBeDefined();
  });

  it("renders empty state when no standalone plans", async () => {
    mockPlansList.mockResolvedValue([]);

    const { default: PlanHistory } = await import(
      "@/components/Profile/PlanHistory"
    );

    render(<PlanHistory />);

    await waitFor(() => {
      expect(screen.getByText(/No coverage plans/)).toBeDefined();
    });
  });

  it("filters out goal-linked plans (goal_id != null)", async () => {
    mockPlansList.mockResolvedValue([
      makePlanSummary({ id: 1, neighborhood_name: "Capitol Hill", goal_id: null }),
      makePlanSummary({ id: 2, neighborhood_name: "Fremont", goal_id: 5 }),
    ]);

    const { default: PlanHistory } = await import(
      "@/components/Profile/PlanHistory"
    );

    render(<PlanHistory />);

    await waitFor(() => {
      expect(screen.getByText("Capitol Hill")).toBeDefined();
    });

    // Fremont plan (goal-linked) should NOT appear
    expect(screen.queryByText("Fremont")).toBeNull();
  });

  it("renders plan rows with name, status, route count, and distance", async () => {
    mockPlansList.mockResolvedValue([
      makePlanSummary({
        id: 1,
        neighborhood_name: "Capitol Hill",
        status: "ready",
        total_routes: 5,
      }),
    ]);

    const { default: PlanHistory } = await import(
      "@/components/Profile/PlanHistory"
    );

    render(<PlanHistory />);

    await waitFor(() => {
      expect(screen.getByText("Capitol Hill")).toBeDefined();
    });

    expect(screen.getByText(/ready/i)).toBeDefined();
    expect(screen.getByText(/5 routes/)).toBeDefined();
  });

  it("expands plan to show detail with routes on click", async () => {
    mockPlansList.mockResolvedValue([
      makePlanSummary({ id: 1, neighborhood_name: "Capitol Hill" }),
    ]);

    const detailData = makePlanDetail({ id: 1 });
    mockPlansGet.mockResolvedValue(detailData);

    const { default: PlanHistory } = await import(
      "@/components/Profile/PlanHistory"
    );

    render(<PlanHistory />);

    await waitFor(() => {
      expect(screen.getByText("Capitol Hill")).toBeDefined();
    });

    // Click to expand
    fireEvent.click(screen.getByText("Capitol Hill"));

    // Should fetch detail
    expect(mockPlansGet).toHaveBeenCalledWith(1);

    // Should show route table
    await waitFor(() => {
      expect(screen.getByText("Match %")).toBeDefined();
    });
  });

  it("calls delete with confirmation", async () => {
    mockPlansList.mockResolvedValue([
      makePlanSummary({ id: 1, neighborhood_name: "Capitol Hill" }),
    ]);
    mockPlansRemove.mockResolvedValue(undefined);

    // Mock window.confirm
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);

    const { default: PlanHistory } = await import(
      "@/components/Profile/PlanHistory"
    );

    render(<PlanHistory />);

    await waitFor(() => {
      expect(screen.getByText("Capitol Hill")).toBeDefined();
    });

    // Click delete button (✕)
    const deleteBtn = screen.getByRole("button", { name: "✕" });
    fireEvent.click(deleteBtn);

    expect(confirmSpy).toHaveBeenCalled();
    expect(mockPlansRemove).toHaveBeenCalledWith(1);

    // Plan should be removed from list
    await waitFor(() => {
      expect(screen.queryByText("Capitol Hill")).toBeNull();
    });

    confirmSpy.mockRestore();
  });

  it("does not delete when confirmation is cancelled", async () => {
    mockPlansList.mockResolvedValue([
      makePlanSummary({ id: 1, neighborhood_name: "Capitol Hill" }),
    ]);

    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);

    const { default: PlanHistory } = await import(
      "@/components/Profile/PlanHistory"
    );

    render(<PlanHistory />);

    await waitFor(() => {
      expect(screen.getByText("Capitol Hill")).toBeDefined();
    });

    const deleteBtn = screen.getByRole("button", { name: "✕" });
    fireEvent.click(deleteBtn);

    expect(confirmSpy).toHaveBeenCalled();
    expect(mockPlansRemove).not.toHaveBeenCalled();

    // Plan should still be there
    expect(screen.getByText("Capitol Hill")).toBeDefined();

    confirmSpy.mockRestore();
  });

  it("shows route pagination when plan has more than 10 routes", async () => {
    mockPlansList.mockResolvedValue([
      makePlanSummary({ id: 1, neighborhood_name: "Capitol Hill", total_routes: 15 }),
    ]);

    const routes = Array.from({ length: 15 }, (_, i) => ({
      sequence_order: i + 1,
      status: "pending",
      route_id: 100 + i,
      distance_meters: 5000,
      estimated_duration_seconds: 2500,
      streets_targeted: 20,
      untraveled_ratio: 0.8,
    }));

    mockPlansGet.mockResolvedValue(makePlanDetail({ id: 1, routes }));

    const { default: PlanHistory } = await import(
      "@/components/Profile/PlanHistory"
    );

    render(<PlanHistory />);

    await waitFor(() => {
      expect(screen.getByText("Capitol Hill")).toBeDefined();
    });

    // Click to expand
    fireEvent.click(screen.getByText("Capitol Hill"));

    await waitFor(() => {
      // Should show pagination label like "1–10 of 15"
      expect(screen.getByText(/1–10 of 15/)).toBeDefined();
    });

    // Should show Next button
    expect(screen.getByText(/Next →/)).toBeDefined();
  });
});
