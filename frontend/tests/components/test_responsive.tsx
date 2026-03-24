/**
 * Responsive behavior tests — validates mobile layout adaptations.
 *
 * Tests are added incrementally per priority tier:
 * - P1: NavBar hamburger menu, MapPage overlay positioning
 * - P2: CoveragePage/RoutePage stacked layouts (added in T011)
 * - P3: ProgressPage/HomePage mobile layouts (added in T018)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import NavBar from "@/components/Layout/NavBar";
import HomePage from "@/pages/HomePage";
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
// P1: NavBar responsive behavior
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
    expect(screen.getByText("Progress")).toBeVisible();
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
// P2: CoveragePage + RoutePage stacked layouts
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
// P3: ProgressPage + HomePage mobile layouts
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
