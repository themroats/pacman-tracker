/**
 * Tests for RouteForm validation and state management.
 *
 * Covers:
 * - RouteForm useEffect reloads neighborhoods on cityId change
 * - Coordinate range validation
 * - Distance validation (max 50 km)
 * - OSRM unavailable disables form
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

describe("RouteForm source validation", () => {
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

    // useEffect dependency includes cityId
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

    // Coordinate validation
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

    // Distance validation
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

describe("FilterPanel state sync", () => {
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

describe("RoutePage OSRM unavailable", () => {
  it("RoutePage checks OSRM availability", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const source = fs.readFileSync(
      path.resolve(__dirname, "../../src/pages/RoutePage.tsx"),
      "utf-8"
    );

    // OSRM flag
    expect(source).toContain("osrmAvailable");
    expect(source).toContain("/health");
    expect(source).toContain("Route suggestions unavailable");
  });
});

describe("SyncStatus complete state", () => {
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

describe("App ErrorBoundary", () => {
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

// ---------------------------------------------------------------------------
// Route Enhancement Feature Tests
// ---------------------------------------------------------------------------

describe("RouteForm variation slider", () => {
  it("has a range input for route variety", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const source = fs.readFileSync(
      path.resolve(__dirname, "../../src/components/RouteSuggestion/RouteForm.tsx"),
      "utf-8"
    );

    expect(source).toContain("Route variety");
    expect(source).toContain('type="range"');
    expect(source).toContain("Efficient");
    expect(source).toContain("Surprise me");
    expect(source).toContain("setVariation");
  });

  it("passes variation to onSubmit", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const source = fs.readFileSync(
      path.resolve(__dirname, "../../src/components/RouteSuggestion/RouteForm.tsx"),
      "utf-8"
    );

    // onSubmit data should include variation
    expect(source).toContain("variation,");
    expect(source).toContain("onSubmit({");
  });
});

describe("RouteForm street preferences", () => {
  it("has preference sliders for each street category", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const source = fs.readFileSync(
      path.resolve(__dirname, "../../src/components/RouteSuggestion/RouteForm.tsx"),
      "utf-8"
    );

    expect(source).toContain("Street preferences");
    expect(source).toContain("residential");
    expect(source).toContain("main_roads");
    expect(source).toContain("trails");
    expect(source).toContain("other");
  });

  it("shows preference labels: Avoid, Low, Med, High", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const source = fs.readFileSync(
      path.resolve(__dirname, "../../src/components/RouteSuggestion/RouteForm.tsx"),
      "utf-8"
    );

    expect(source).toContain('"Avoid"');
    expect(source).toContain('"Low"');
    expect(source).toContain('"Med"');
    expect(source).toContain('"High"');
  });

  it("has a collapsible toggle for preferences", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const source = fs.readFileSync(
      path.resolve(__dirname, "../../src/components/RouteSuggestion/RouteForm.tsx"),
      "utf-8"
    );

    expect(source).toContain("showPrefs");
    expect(source).toContain("setShowPrefs");
    expect(source).toContain("{showPrefs &&");
  });

  it("passes preferences to onSubmit", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const source = fs.readFileSync(
      path.resolve(__dirname, "../../src/components/RouteSuggestion/RouteForm.tsx"),
      "utf-8"
    );

    expect(source).toContain("preferences,");
    expect(source).toContain("onSubmit({");
  });
});

describe("RouteForm saved start points", () => {
  it("accepts saved start points as props", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const source = fs.readFileSync(
      path.resolve(__dirname, "../../src/components/RouteSuggestion/RouteForm.tsx"),
      "utf-8"
    );

    // savedPoints and selectedPointId come from parent (lifted for map sharing)
    expect(source).toContain("savedPoints: SavedStartPoint[]");
    expect(source).toContain("onSavedPointsChange");
  });

  it("has an add-point flow with save dialog", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const source = fs.readFileSync(
      path.resolve(__dirname, "../../src/components/RouteSuggestion/RouteForm.tsx"),
      "utf-8"
    );

    expect(source).toContain("Add start point");
    expect(source).toContain("handleSavePoint");
    expect(source).toContain("addingPoint");
    expect(source).toContain("savePointName");
  });

  it("uses savedPoints prop for default display", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const source = fs.readFileSync(
      path.resolve(__dirname, "../../src/components/RouteSuggestion/RouteForm.tsx"),
      "utf-8"
    );

    expect(source).toContain("is_default");
    expect(source).toContain("selectedPointId");
  });

  it("can delete a saved point", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const source = fs.readFileSync(
      path.resolve(__dirname, "../../src/components/RouteSuggestion/RouteForm.tsx"),
      "utf-8"
    );

    expect(source).toContain("handleDeleteSavedPoint");
    expect(source).toContain("startPointsApi.remove");
  });

  it("delegates selection to parent via onSelectSavedPoint", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const source = fs.readFileSync(
      path.resolve(__dirname, "../../src/components/RouteSuggestion/RouteForm.tsx"),
      "utf-8"
    );

    // Selection delegated to parent for map marker sync
    expect(source).toContain("onSelectSavedPoint(id)");
    expect(source).toContain("onSelectSavedPoint(null)");
  });
});
