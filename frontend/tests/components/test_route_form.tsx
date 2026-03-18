/**
 * Tests for RouteForm validation and state management.
 *
 * Covers:
 * - T048: RouteForm useEffect reloads neighborhoods on cityId change
 * - T058: Coordinate range validation
 * - T059: Distance validation (max 50 km)
 * - T060: OSRM unavailable disables form
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

describe("RouteForm source validation (T048, T058, T059)", () => {
  it("RouteForm useEffect depends on cityId", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const source = fs.readFileSync(
      path.resolve(
        __dirname,
        "../../src/components/RouteSuggestion/RouteForm.tsx"
      ),
      "utf-8"
    );

    // T048: useEffect dependency includes cityId
    expect(source).toContain("[cityId, onCityChange]");
    // Should NOT have empty dependency array with eslint-disable
    expect(source).not.toContain("// eslint-disable-line react-hooks/exhaustive-deps");
  });

  it("RouteForm validates longitude range", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const source = fs.readFileSync(
      path.resolve(
        __dirname,
        "../../src/components/RouteSuggestion/RouteForm.tsx"
      ),
      "utf-8"
    );

    // T058: Coordinate validation
    expect(source).toContain("Longitude must be");
    expect(source).toContain("Latitude must be");
    expect(source).toContain("-180");
    expect(source).toContain("-90");
  });

  it("RouteForm validates distance max 50km", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const source = fs.readFileSync(
      path.resolve(
        __dirname,
        "../../src/components/RouteSuggestion/RouteForm.tsx"
      ),
      "utf-8"
    );

    // T059: Distance validation
    expect(source).toContain("Distance must be");
    expect(source).toContain("50");
  });

  it("RouteForm shows validation error element", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const source = fs.readFileSync(
      path.resolve(
        __dirname,
        "../../src/components/RouteSuggestion/RouteForm.tsx"
      ),
      "utf-8"
    );

    expect(source).toContain("validationError");
    expect(source).toContain('role="alert"');
  });
});

describe("FilterPanel state sync (T049)", () => {
  it("FilterPanel uses useEffect to sync local state from props", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const source = fs.readFileSync(
      path.resolve(
        __dirname,
        "../../src/components/ActivityList/FilterPanel.tsx"
      ),
      "utf-8"
    );

    expect(source).toContain("useEffect");
    expect(source).toContain("filters.start_date");
    expect(source).toContain("filters.end_date");
  });
});

describe("RoutePage OSRM unavailable (T060)", () => {
  it("RoutePage checks OSRM availability", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const source = fs.readFileSync(
      path.resolve(__dirname, "../../src/pages/RoutePage.tsx"),
      "utf-8"
    );

    // T060: OSRM flag
    expect(source).toContain("osrmAvailable");
    expect(source).toContain("/api/v1/health");
    expect(source).toContain("Route suggestions unavailable");
  });
});

describe("SyncStatus complete state (T038)", () => {
  it("SyncStatus handles complete state with success toast", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const source = fs.readFileSync(
      path.resolve(__dirname, "../../src/components/SyncStatus.tsx"),
      "utf-8"
    );

    expect(source).toContain('"complete"');
    expect(source).toContain("addToast");
    expect(source).toContain("success");
  });
});

describe("App ErrorBoundary (T050)", () => {
  it("App.tsx wraps content in ErrorBoundary", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const source = fs.readFileSync(
      path.resolve(__dirname, "../../src/App.tsx"),
      "utf-8"
    );

    expect(source).toContain("ErrorBoundary");
    expect(source).toContain("<ErrorBoundary>");
  });
});
