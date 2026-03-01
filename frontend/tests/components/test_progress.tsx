/**
 * T094 — Frontend progress timeline component tests.
 *
 * Tests: TimelineChart, MilestoneList, StatsOverview rendering and data display.
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

// ---------------------------------------------------------------------------
// TimelineChart
// ---------------------------------------------------------------------------

describe("TimelineChart", () => {
  it("renders timeline entries as data points", async () => {
    const { default: TimelineChart } = await import(
      "@/components/ProgressTimeline/TimelineChart"
    );

    const timeline = [
      { date: "2025-01-01", coverage_percentage: 5.0, streets_traveled: 50 },
      { date: "2025-02-01", coverage_percentage: 12.3, streets_traveled: 123 },
    ];

    render(<TimelineChart timeline={timeline} />);

    // Should display dates
    expect(screen.getByText(/2025-01-01/)).toBeDefined();
    expect(screen.getByText(/2025-02-01/)).toBeDefined();
  });

  it("shows empty state when no data", async () => {
    const { default: TimelineChart } = await import(
      "@/components/ProgressTimeline/TimelineChart"
    );

    render(<TimelineChart timeline={[]} />);
    expect(screen.getByText(/no data/i)).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// MilestoneList
// ---------------------------------------------------------------------------

describe("MilestoneList", () => {
  it("renders milestone badges with dates", async () => {
    const { default: MilestoneList } = await import(
      "@/components/ProgressTimeline/MilestoneList"
    );

    const milestones = [
      { label: "25%", neighborhood_name: "Capitol Hill", reached: true, date: "2025-02-01" },
      { label: "50%", neighborhood_name: "Capitol Hill", reached: false, date: null },
    ];

    render(<MilestoneList milestones={milestones} />);

    expect(screen.getByText("25%")).toBeDefined();
    expect(screen.getByText("50%")).toBeDefined();
    expect(screen.getByText(/Capitol Hill/)).toBeDefined();
  });

  it("visually differentiates reached and unreached milestones", async () => {
    const { default: MilestoneList } = await import(
      "@/components/ProgressTimeline/MilestoneList"
    );

    const milestones = [
      { label: "25%", neighborhood_name: "Test", reached: true, date: "2025-01-01" },
      { label: "50%", neighborhood_name: "Test", reached: false, date: null },
    ];

    render(<MilestoneList milestones={milestones} />);

    // Reached milestone should show date
    expect(screen.getByText("2025-01-01")).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// StatsOverview
// ---------------------------------------------------------------------------

describe("StatsOverview", () => {
  it("renders overall statistics", async () => {
    const { default: StatsOverview } = await import(
      "@/components/ProgressTimeline/StatsOverview"
    );

    const stats = {
      total_activities: 234,
      total_distance_meters: 1850000,
      total_unique_streets: 1250,
      cities: [
        {
          city_name: "Seattle",
          coverage_percentage: 12.5,
          streets_traveled: 1250,
          streets_total: 10000,
        },
      ],
    };

    render(<StatsOverview stats={stats} />);

    expect(screen.getByText("234")).toBeDefined();
    expect(screen.getByText("1,250")).toBeDefined();
    expect(screen.getByText(/Seattle/)).toBeDefined();
  });
});
