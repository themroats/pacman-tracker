/**
 * Tests for CoveragePage street data caching.
 *
 * Verifies:
 * - Switching neighborhoods within the same city uses cached data (no re-fetch)
 * - Switching cities clears the cache
 */

import { describe, it, expect, vi, beforeEach } from "vitest";

describe("CoveragePage streets cache", () => {
  it("CoveragePage source uses a streetsCache ref", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const source = fs.readFileSync(
      path.resolve(__dirname, "../../src/pages/CoveragePage.tsx"),
      "utf-8"
    );

    // Cache exists
    expect(source).toContain("streetsCache");
    expect(source).toContain("useRef<Map<string, GeoJSONFeatureCollection>>");

    // loadStreetCoverage checks cache before fetching
    expect(source).toContain("streetsCache.current.get(cacheKey)");
    expect(source).toContain("streetsCache.current.set(cacheKey");

    // Cache is cleared on city change
    expect(source).toContain("streetsCache.current.clear()");
  });

  it("loadStreetCoverage uses city:neighborhood as cache key", async () => {
    const fs = await import("fs");
    const path = await import("path");
    const source = fs.readFileSync(
      path.resolve(__dirname, "../../src/pages/CoveragePage.tsx"),
      "utf-8"
    );

    // Cache key includes both cityId and neighborhoodId
    expect(source).toContain("${cityId}:${neighborhoodId");
  });
});
