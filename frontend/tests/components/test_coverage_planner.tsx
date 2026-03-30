/**
 * Tests for CoveragePlanner components.
 *
 * Covers:
 * - NeighborhoodPlanForm: 100% complete state, generate button, distance input
 * - PlanDetail: route list, GPX buttons
 * - CoverageGoalForm: target/distance inputs, validation
 * - GoalDetail: neighborhood list, view plan button
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";

// ---------------------------------------------------------------------------
// NeighborhoodPlanForm
// ---------------------------------------------------------------------------

describe("NeighborhoodPlanForm", () => {
  it("shows completion message when 100% covered", async () => {
    const { default: NeighborhoodPlanForm } = await import(
      "@/components/CoveragePlanner/NeighborhoodPlanForm"
    );

    render(
      <NeighborhoodPlanForm
        neighborhoodId={1}
        neighborhoodName="Capitol Hill"
        cityId={1}
        coveragePct={100}
        onPlanCreated={vi.fn()}
      />,
    );

    expect(screen.getByText(/100% complete/)).toBeDefined();
  });

  it("shows generate button when not fully covered", async () => {
    const { startPointsApi } = await import("@/api/client");
    vi.spyOn(startPointsApi, "list").mockResolvedValue([
      { id: 10, name: "Home", lng: -122.33, lat: 47.61, is_default: true },
    ]);

    const { default: NeighborhoodPlanForm } = await import(
      "@/components/CoveragePlanner/NeighborhoodPlanForm"
    );

    render(
      <NeighborhoodPlanForm
        neighborhoodId={1}
        neighborhoodName="Capitol Hill"
        cityId={1}
        coveragePct={45.2}
        onPlanCreated={vi.fn()}
      />,
    );

    expect(screen.getByText(/Generate Coverage Plan/)).toBeDefined();
    expect(screen.getByText(/45.2%/)).toBeDefined();
  });

  it("has distance input with default value", async () => {
    const { startPointsApi } = await import("@/api/client");
    vi.spyOn(startPointsApi, "list").mockResolvedValue([
      { id: 10, name: "Home", lng: -122.33, lat: 47.61, is_default: true },
    ]);

    const { default: NeighborhoodPlanForm } = await import(
      "@/components/CoveragePlanner/NeighborhoodPlanForm"
    );

    render(
      <NeighborhoodPlanForm
        neighborhoodId={1}
        neighborhoodName="Capitol Hill"
        cityId={1}
        coveragePct={50}
        onPlanCreated={vi.fn()}
      />,
    );

    const input = screen.getByRole("spinbutton");
    expect((input as HTMLInputElement).value).toBe("5");
  });

  it("calls plansApi and onPlanCreated on submit", async () => {
    const mockPlan = {
      id: 1,
      neighborhood_id: 1,
      neighborhood_name: "Capitol Hill",
      city_id: 1,
      status: "ready",
      preferred_route_distance_m: 5000,
      initial_coverage_pct: 50,
      target_coverage_pct: 100,
      total_routes: 2,
      total_distance_m: 10000,
      error_message: null,
      routes: [],
    };

    const { plansApi, startPointsApi } = await import("@/api/client");
    vi.spyOn(startPointsApi, "list").mockResolvedValue([
      { id: 10, name: "Home", lng: -122.33, lat: 47.61, is_default: true },
    ]);
    vi.spyOn(plansApi, "createNeighborhood").mockResolvedValue(mockPlan);

    const onPlanCreated = vi.fn();
    const { default: NeighborhoodPlanForm } = await import(
      "@/components/CoveragePlanner/NeighborhoodPlanForm"
    );

    render(
      <NeighborhoodPlanForm
        neighborhoodId={1}
        neighborhoodName="Capitol Hill"
        cityId={1}
        coveragePct={50}
        onPlanCreated={onPlanCreated}
      />,
    );

    // Wait for start points to load
    await waitFor(() => {
      expect(screen.getByText(/Home/)).toBeDefined();
    });

    fireEvent.click(screen.getByText(/Generate Coverage Plan/));

    await waitFor(() => {
      expect(plansApi.createNeighborhood).toHaveBeenCalledWith({
        neighborhood_id: 1,
        city_id: 1,
        preferred_route_distance_m: 5000,
        start_point_id: 10,
      });
      expect(onPlanCreated).toHaveBeenCalledWith(mockPlan);
    });
  });

  it("shows error on API failure", async () => {
    const { plansApi, startPointsApi } = await import("@/api/client");
    vi.spyOn(startPointsApi, "list").mockResolvedValue([
      { id: 10, name: "Home", lng: -122.33, lat: 47.61, is_default: true },
    ]);
    vi.spyOn(plansApi, "createNeighborhood").mockRejectedValue(new Error("OSRM down"));

    const { default: NeighborhoodPlanForm } = await import(
      "@/components/CoveragePlanner/NeighborhoodPlanForm"
    );

    render(
      <NeighborhoodPlanForm
        neighborhoodId={1}
        neighborhoodName="Capitol Hill"
        cityId={1}
        coveragePct={50}
        onPlanCreated={vi.fn()}
      />,
    );

    // Wait for start points to load
    await waitFor(() => {
      expect(screen.getByText(/Home/)).toBeDefined();
    });

    fireEvent.click(screen.getByText(/Generate Coverage Plan/));

    await waitFor(() => {
      expect(screen.getByText(/OSRM down/)).toBeDefined();
    });
  });
});

// ---------------------------------------------------------------------------
// PlanDetail
// ---------------------------------------------------------------------------

describe("PlanDetail", () => {
  const mockPlan = {
    id: 1,
    neighborhood_id: 1,
    neighborhood_name: "Fremont",
    city_id: 1,
    status: "ready" as const,
    preferred_route_distance_m: 5000,
    initial_coverage_pct: 30,
    target_coverage_pct: 100,
    total_routes: 3,
    total_distance_m: 15000,
    error_message: null,
    routes: [
      { sequence_order: 1, status: "completed", route_id: 101, distance_meters: 5000, estimated_duration_seconds: 2500, streets_targeted: 12, untraveled_ratio: 0.8 },
      { sequence_order: 2, status: "pending", route_id: 102, distance_meters: 5200, estimated_duration_seconds: 2600, streets_targeted: 10, untraveled_ratio: 0.75 },
      { sequence_order: 3, status: "pending", route_id: 103, distance_meters: 4800, estimated_duration_seconds: 2400, streets_targeted: 8, untraveled_ratio: 0.7 },
    ],
  };

  it("renders neighborhood name and stats", async () => {
    const { default: PlanDetail } = await import(
      "@/components/CoveragePlanner/PlanDetail"
    );

    render(<PlanDetail plan={mockPlan} />);

    expect(screen.getByText("Fremont")).toBeDefined();
    expect(screen.getByText(/3 routes ·/)).toBeDefined();
    expect(screen.getByText(/15.0 km/)).toBeDefined();
  });

  it("renders route list with distance and duration", async () => {
    const { default: PlanDetail } = await import(
      "@/components/CoveragePlanner/PlanDetail"
    );

    render(<PlanDetail plan={mockPlan} />);

    expect(screen.getByText("Route 1")).toBeDefined();
    expect(screen.getByText("Route 2")).toBeDefined();
    expect(screen.getByText("Route 3")).toBeDefined();
    // Route 2: 5.2 km · 43 min · 10 streets
    expect(screen.getByText(/5.2 km/)).toBeDefined();
  });

  it("shows GPX button for every route", async () => {
    const { default: PlanDetail } = await import(
      "@/components/CoveragePlanner/PlanDetail"
    );

    render(<PlanDetail plan={mockPlan} />);

    const gpxButtons = screen.getAllByText("GPX");
    expect(gpxButtons.length).toBe(3);
  });

  it("shows status badge", async () => {
    const { default: PlanDetail } = await import(
      "@/components/CoveragePlanner/PlanDetail"
    );

    render(<PlanDetail plan={mockPlan} />);

    expect(screen.getByText("ready")).toBeDefined();
  });

  it("shows error message when present", async () => {
    const { default: PlanDetail } = await import(
      "@/components/CoveragePlanner/PlanDetail"
    );

    const failedPlan = {
      ...mockPlan,
      status: "failed",
      error_message: "OSRM connection refused",
      routes: [],
      total_routes: 0,
    };

    render(<PlanDetail plan={failedPlan} />);

    expect(screen.getByText("OSRM connection refused")).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// CoverageGoalForm
// ---------------------------------------------------------------------------

describe("CoverageGoalForm", () => {
  it("renders with city name and current coverage", async () => {
    const { default: CoverageGoalForm } = await import(
      "@/components/CoveragePlanner/CoverageGoalForm"
    );

    render(
      <CoverageGoalForm
        cityId={1}
        cityName="Seattle"
        currentCoveragePct={35.5}
        onGoalCreated={vi.fn()}
      />,
    );

    expect(screen.getByText(/Coverage Goal for Seattle/)).toBeDefined();
    expect(screen.getByText(/35.5%/)).toBeDefined();
  });

  it("has target and distance inputs", async () => {
    const { default: CoverageGoalForm } = await import(
      "@/components/CoveragePlanner/CoverageGoalForm"
    );

    render(
      <CoverageGoalForm
        cityId={1}
        cityName="Seattle"
        currentCoveragePct={35}
        onGoalCreated={vi.fn()}
      />,
    );

    const inputs = screen.getAllByRole("spinbutton");
    expect(inputs.length).toBe(2); // target % and distance
  });

  it("defaults target to current + 10", async () => {
    const { default: CoverageGoalForm } = await import(
      "@/components/CoveragePlanner/CoverageGoalForm"
    );

    render(
      <CoverageGoalForm
        cityId={1}
        cityName="Seattle"
        currentCoveragePct={35}
        onGoalCreated={vi.fn()}
      />,
    );

    const inputs = screen.getAllByRole("spinbutton");
    expect((inputs[0] as HTMLInputElement).value).toBe("45");
  });

  it("shows submit button", async () => {
    const { default: CoverageGoalForm } = await import(
      "@/components/CoveragePlanner/CoverageGoalForm"
    );

    render(
      <CoverageGoalForm
        cityId={1}
        cityName="Seattle"
        currentCoveragePct={35}
        onGoalCreated={vi.fn()}
      />,
    );

    expect(screen.getByText(/Find Optimal Plan/)).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// GoalDetail
// ---------------------------------------------------------------------------

describe("GoalDetail", () => {
  const mockGoal = {
    id: 1,
    city_id: 1,
    target_coverage_pct: 50,
    current_coverage_pct: 35,
    status: "ready",
    total_routes: 8,
    total_distance_m: 40000,
    neighborhoods: [
      {
        neighborhood_id: 1,
        neighborhood_name: "Capitol Hill",
        current_coverage_pct: 20,
        untraveled_streets: 45,
        untraveled_distance_m: 9000,
        plan_id: 101,
        plan_status: "ready",
        estimated_routes: 3,
      },
      {
        neighborhood_id: 2,
        neighborhood_name: "Fremont",
        current_coverage_pct: 40,
        untraveled_streets: 30,
        untraveled_distance_m: 6000,
        plan_id: 102,
        plan_status: "ready",
        estimated_routes: 2,
      },
    ],
  };

  it("renders target coverage heading", async () => {
    const { default: GoalDetail } = await import(
      "@/components/CoveragePlanner/GoalDetail"
    );

    render(<GoalDetail goal={mockGoal} onViewPlan={vi.fn()} />);

    expect(screen.getByText(/Reach 50% Coverage/)).toBeDefined();
  });

  it("shows total routes and distance", async () => {
    const { default: GoalDetail } = await import(
      "@/components/CoveragePlanner/GoalDetail"
    );

    render(<GoalDetail goal={mockGoal} onViewPlan={vi.fn()} />);

    expect(screen.getByText(/8 routes/)).toBeDefined();
    expect(screen.getByText(/40.0 km/)).toBeDefined();
  });

  it("lists neighborhoods with coverage stats", async () => {
    const { default: GoalDetail } = await import(
      "@/components/CoveragePlanner/GoalDetail"
    );

    render(<GoalDetail goal={mockGoal} onViewPlan={vi.fn()} />);

    expect(screen.getByText("Capitol Hill")).toBeDefined();
    expect(screen.getByText("Fremont")).toBeDefined();
    expect(screen.getByText(/45 streets left/)).toBeDefined();
  });

  it("has view plan buttons for neighborhoods with plans", async () => {
    const { default: GoalDetail } = await import(
      "@/components/CoveragePlanner/GoalDetail"
    );

    render(<GoalDetail goal={mockGoal} onViewPlan={vi.fn()} />);

    const viewBtns = screen.getAllByText(/View plan/);
    expect(viewBtns.length).toBe(2);
  });

  it("calls onViewPlan when View plan clicked", async () => {
    const { default: GoalDetail } = await import(
      "@/components/CoveragePlanner/GoalDetail"
    );

    const onViewPlan = vi.fn();
    render(<GoalDetail goal={mockGoal} onViewPlan={onViewPlan} />);

    const viewBtns = screen.getAllByText(/View plan/);
    fireEvent.click(viewBtns[0]);
    expect(onViewPlan).toHaveBeenCalledWith(101);
  });

  it("shows completion message when goal is completed", async () => {
    const { default: GoalDetail } = await import(
      "@/components/CoveragePlanner/GoalDetail"
    );

    const completedGoal = {
      ...mockGoal,
      status: "completed",
      current_coverage_pct: 55,
    };

    render(<GoalDetail goal={completedGoal} onViewPlan={vi.fn()} />);

    expect(screen.getByText(/already reached 55.0% coverage/)).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// Source-level tests for CoveragePage planner integration
// ---------------------------------------------------------------------------

describe("CoveragePage planner wiring", () => {
  it("imports all planner components", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const source = fs.readFileSync(
      path.resolve(__dirname, "../../src/pages/CoveragePage.tsx"),
      "utf-8"
    );

    expect(source).toContain("NeighborhoodPlanForm");
    expect(source).toContain("PlanDetail");
    expect(source).toContain("CoverageGoalForm");
    expect(source).toContain("GoalDetail");
  });

  it("imports plansApi and goalsApi", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const source = fs.readFileSync(
      path.resolve(__dirname, "../../src/pages/CoveragePage.tsx"),
      "utf-8"
    );

    expect(source).toContain("plansApi");
    expect(source).toContain("goalsApi");
  });

  it("has planner view state management", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const source = fs.readFileSync(
      path.resolve(__dirname, "../../src/pages/CoveragePage.tsx"),
      "utf-8"
    );

    expect(source).toContain("plannerView");
    expect(source).toContain("activePlan");
    expect(source).toContain("activeGoal");
    expect(source).toContain("plan-form");
    expect(source).toContain("plan-detail");
    expect(source).toContain("goal-form");
    expect(source).toContain("goal-detail");
  });

  it("has a Set Coverage Goal button", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const source = fs.readFileSync(
      path.resolve(__dirname, "../../src/pages/CoveragePage.tsx"),
      "utf-8"
    );

    expect(source).toContain("Set Coverage Goal");
  });
});
