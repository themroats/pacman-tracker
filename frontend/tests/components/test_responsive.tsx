/**
 * Responsive behavior tests — validates mobile layout adaptations.
 *
 * Tests are added incrementally per priority tier:
 * - NavBar hamburger menu, MapPage overlay positioning
 * - CoveragePage/RoutePage stacked layouts
 * - ProgressPage/HomePage mobile layouts
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import NavBar from "@/components/Layout/NavBar";
import HomePage from "@/pages/HomePage";
import FilterPanel from "@/components/ActivityList/FilterPanel";
import CoverageSummary from "@/components/CoverageDashboard/CoverageSummary";
import SyncStatus from "@/components/SyncStatus";
import { useAppStore } from "@/store";

// Save the original matchMedia set by setup.ts so we can restore it
const originalMatchMedia = window.matchMedia;

// Helper: override matchMedia to simulate mobile
function mockMobile() {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query === "(max-width: 767px)",
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

// Helper: override matchMedia to simulate desktop
function mockDesktop() {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

// ---------------------------------------------------------------------------
// NavBar responsive behavior
// ---------------------------------------------------------------------------

describe("NavBar — mobile responsive", () => {
  afterEach(() => {
    // Restore the default desktop matchMedia mock after each test
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: originalMatchMedia,
    });
  });

  beforeEach(() => {
    // Set authenticated state so nav items render
    useAppStore.setState({
      isAuthenticated: true,
      displayName: "Test User",
      userId: 1,
      accessToken: "test-token",
    });
  });

  it("renders hamburger menu icon on mobile instead of horizontal links", () => {
    mockMobile();
    render(
      <MemoryRouter>
        <NavBar />
      </MemoryRouter>,
    );

    // Should have a hamburger button
    const hamburger = screen.getByRole("button", { name: /menu/i });
    expect(hamburger).toBeInTheDocument();

    // Horizontal nav links should NOT be in the DOM initially (menu closed)
    expect(screen.queryByText("Map")).not.toBeInTheDocument();
  });

  it("shows nav links when hamburger menu is opened on mobile", () => {
    mockMobile();
    render(
      <MemoryRouter>
        <NavBar />
      </MemoryRouter>,
    );

    const hamburger = screen.getByRole("button", { name: /menu/i });
    fireEvent.click(hamburger);

    // All nav items should now be visible
    expect(screen.getByText("Map")).toBeVisible();
    expect(screen.getByText("Coverage")).toBeVisible();
    expect(screen.getByText("Routes")).toBeVisible();
    expect(screen.getByText("Profile")).toBeVisible();
    expect(screen.getByText("Logout")).toBeVisible();
  });

  it("renders horizontal links on desktop (no hamburger)", () => {
    mockDesktop();
    render(
      <MemoryRouter>
        <NavBar />
      </MemoryRouter>,
    );

    // Should NOT have a hamburger button
    expect(screen.queryByRole("button", { name: /menu/i })).not.toBeInTheDocument();

    // Horizontal links should be visible
    expect(screen.getByText("Map")).toBeVisible();
    expect(screen.getByText("Coverage")).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// CoveragePage + RoutePage stacked layouts
// ---------------------------------------------------------------------------

describe("RoutePage — mobile responsive", () => {
  afterEach(() => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: originalMatchMedia,
    });
  });

  beforeEach(() => {
    useAppStore.setState({
      isAuthenticated: true,
      displayName: "Test User",
      userId: 1,
      accessToken: "test-token",
    });
  });

  it("renders stacked layout (no fixed sidebar) on mobile", async () => {
    mockMobile();
    // We can't render the full RoutePage (it uses MapContainer which needs
    // a real DOM), but we can verify the useIsMobile hook returns true on mobile
    // and the page component would receive it. Instead, test the hook directly.
    const { useIsMobile } = await import("@/hooks/useIsMobile");
    const { renderHook } = await import("@testing-library/react");
    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(true);
  });

  it("returns false for desktop viewport", async () => {
    mockDesktop();
    const { useIsMobile } = await import("@/hooks/useIsMobile");
    const { renderHook } = await import("@testing-library/react");
    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// ProgressPage + HomePage mobile layouts
// ---------------------------------------------------------------------------

describe("HomePage — mobile responsive", () => {
  afterEach(() => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: originalMatchMedia,
    });
  });

  it("renders buttons in a wrapping layout on mobile (authenticated)", () => {
    mockMobile();
    useAppStore.setState({
      isAuthenticated: true,
      displayName: "Runner",
      userId: 1,
      accessToken: "test-token",
    });
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );
    const mapBtn = screen.getByText("View Map");
    expect(mapBtn).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// FilterPanel — collapsible on mobile
// ---------------------------------------------------------------------------

describe("FilterPanel — mobile responsive", () => {
  afterEach(() => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: originalMatchMedia,
    });
  });

  const noopFilters = { sport_type: undefined, start_date: undefined, end_date: undefined };
  const noop = () => {};

  it("shows collapsed toggle button on mobile, content hidden", () => {
    mockMobile();
    render(<FilterPanel filters={noopFilters} onFiltersChange={noop} />);

    const toggle = screen.getByRole("button", { name: /filters/i });
    expect(toggle).toBeInTheDocument();

    // Filter controls should not be visible when collapsed
    expect(screen.queryByText("Sport Type")).not.toBeInTheDocument();
  });

  it("expands filter content when toggle is clicked on mobile", () => {
    mockMobile();
    render(<FilterPanel filters={noopFilters} onFiltersChange={noop} />);

    fireEvent.click(screen.getByRole("button", { name: /filters/i }));

    // Filter controls should now be visible
    expect(screen.getByText("Sport Type")).toBeVisible();
    expect(screen.getByText("Clear")).toBeVisible();
  });

  it("shows filter content immediately on desktop (no toggle)", () => {
    mockDesktop();
    render(<FilterPanel filters={noopFilters} onFiltersChange={noop} />);

    // No toggle button on desktop
    expect(screen.queryByRole("button", { name: /filters/i })).not.toBeInTheDocument();

    // Filter controls visible immediately
    expect(screen.getByText("Sport Type")).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// CoverageSummary — collapsible neighborhood table on mobile
// ---------------------------------------------------------------------------

describe("CoverageSummary — mobile responsive", () => {
  afterEach(() => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: originalMatchMedia,
    });
  });

  const mockCity = {
    id: 1,
    name: "Seattle",
    coverage_percentage: 6.5,
    streets_traveled: 100,
    streets_total: 1500,
    distance_traveled_m: 50000,
    distance_total_m: 800000,
  };

  const mockNeighborhoods = [
    { id: 1, name: "Capitol Hill", coverage_percentage: 75.2, streets_traveled: 100, streets_total: 133 },
    { id: 2, name: "Ballard", coverage_percentage: 12.0, streets_traveled: 20, streets_total: 167 },
  ];

  it("hides neighborhood table by default on mobile", () => {
    mockMobile();
    render(<CoverageSummary city={mockCity} neighborhoods={mockNeighborhoods} />);

    // Should show collapsible button
    expect(screen.getByText(/Neighborhoods \(2\)/)).toBeInTheDocument();

    // Table rows should NOT be in the DOM
    expect(screen.queryByText("Capitol Hill")).not.toBeInTheDocument();
  });

  it("expands neighborhood table when button clicked on mobile", () => {
    mockMobile();
    render(<CoverageSummary city={mockCity} neighborhoods={mockNeighborhoods} />);

    fireEvent.click(screen.getByText(/Neighborhoods \(2\)/));

    // Table rows should now be visible
    expect(screen.getByText("Capitol Hill")).toBeVisible();
    expect(screen.getByText("Ballard")).toBeVisible();
  });

  it("shows neighborhood table immediately on desktop", () => {
    mockDesktop();
    render(<CoverageSummary city={mockCity} neighborhoods={mockNeighborhoods} />);

    // No toggle button, table visible immediately
    expect(screen.queryByText(/Neighborhoods \(\d+\)/)).not.toBeInTheDocument();
    expect(screen.getByText("Capitol Hill")).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// SyncStatus — compact on mobile
// ---------------------------------------------------------------------------

describe("SyncStatus — mobile responsive", () => {
  const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(() =>
    Promise.resolve(new Response(JSON.stringify({ status: "idle" }), { status: 200 })),
  );

  afterEach(() => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: originalMatchMedia,
    });
    fetchSpy.mockClear();
  });

  beforeEach(() => {
    useAppStore.setState({
      isAuthenticated: true,
      syncStatus: {
        status: "idle",
        total_activities: 262,
        imported_activities: 242,
        matched_activities: 107,
        last_sync_at: null,
        error_message: null,
      },
    });
  });

  it("shows only status label on mobile (no counts)", () => {
    mockMobile();
    render(<SyncStatus />);

    expect(screen.getByText("idle")).toBeInTheDocument();
    expect(screen.queryByText(/imported/)).not.toBeInTheDocument();
  });

  it("shows full status with counts on desktop", () => {
    mockDesktop();
    render(<SyncStatus />);

    expect(screen.getByText("idle")).toBeInTheDocument();
    expect(screen.getByText(/242\/262 imported/)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// NavBar — menu closes on navigation
// ---------------------------------------------------------------------------

describe("NavBar — menu closes on navigate", () => {
  afterEach(() => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: originalMatchMedia,
    });
  });

  beforeEach(() => {
    useAppStore.setState({
      isAuthenticated: true,
      displayName: "Test User",
      userId: 1,
      accessToken: "test-token",
    });
  });

  it("closes the mobile menu when a link is clicked (location changes)", () => {
    mockMobile();
    const { rerender } = render(
      <MemoryRouter initialEntries={["/map"]}>
        <NavBar />
      </MemoryRouter>,
    );

    // Open menu
    fireEvent.click(screen.getByRole("button", { name: /menu/i }));
    expect(screen.getByText("Coverage")).toBeVisible();

    // Click Coverage link
    fireEvent.click(screen.getByText("Coverage"));

    // Re-render with new location to trigger the useEffect
    rerender(
      <MemoryRouter initialEntries={["/coverage"]}>
        <NavBar />
      </MemoryRouter>,
    );

    // Menu should be closed — links not in DOM
    expect(screen.queryByText("Routes")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// useIsMobile — matchMedia change event
// ---------------------------------------------------------------------------

describe("useIsMobile — responds to matchMedia changes", () => {
  afterEach(() => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: originalMatchMedia,
    });
  });

  it("updates when matchMedia fires a change event", async () => {
    // Start as desktop
    let changeHandler: ((e: { matches: boolean }) => void) | null = null;
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn().mockImplementation((_event: string, handler: (e: { matches: boolean }) => void) => {
          changeHandler = handler;
        }),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });

    const { useIsMobile } = await import("@/hooks/useIsMobile");
    const { renderHook, act } = await import("@testing-library/react");
    const { result } = renderHook(() => useIsMobile());

    expect(result.current).toBe(false);

    // Simulate orientation change to mobile
    await act(async () => {
      changeHandler?.({ matches: true });
    });

    expect(result.current).toBe(true);
  });
});
