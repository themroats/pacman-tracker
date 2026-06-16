import { test, expect } from "@playwright/test";
import { seedAuth } from "./helpers/auth";
import { startEvidence, makeResult } from "./helpers/evidence";

/**
 * User Story 1 (P1) — Verify a protected-page fix in a real browser without
 * Strava OAuth.
 *
 * Prerequisites: the warm verification stack is running (infra/verify-up.ps1),
 * i.e. backend on :8000 with DEV_AUTH_BYPASS=1 and the seeded demo user, and the
 * frontend dev server on :5173.
 */

test.describe("US1 — reach protected pages without OAuth", () => {
  test.beforeEach(async ({ page }) => {
    // Seed the authenticated demo session BEFORE any navigation so the app does
    // not redirect to the Strava login screen (acceptance 1).
    await seedAuth(page);
  });

  test("coverage dashboard renders as the demo user (no login redirect)", async ({ page }) => {
    const finalize = startEvidence(page);

    await page.goto("/coverage");

    // Did NOT bounce back to the landing/login screen.
    await expect(page).toHaveURL(/\/coverage$/);

    // The dashboard chrome is present (not an unauthenticated "connect Strava" prompt).
    await expect(page.getByText(/connect.*strava/i)).toHaveCount(0);

    const evidence = await finalize();
    const result = makeResult(
      evidence,
      (e) => /\/coverage$/.test(page.url()) && e.consoleErrors.length === 0,
      "Coverage dashboard reached and rendered without OAuth.",
    );
    expect(result.outcome, JSON.stringify(result.evidence, null, 2)).toBe("pass");
  });

  test("map page renders as the demo user", async ({ page }) => {
    await page.goto("/map");
    await expect(page).toHaveURL(/\/map$/);
    // Leaflet map container mounts on the protected map page.
    await expect(page.locator(".leaflet-container")).toBeVisible();
  });

  test("interacting with the coverage page is observable (acceptance 2)", async ({ page }) => {
    const finalize = startEvidence(page);
    await page.goto("/coverage");

    // Exercise a control the user would use — the city/area selector.
    const selector = page.getByRole("combobox").first();
    await expect(selector).toBeVisible();
    await selector.click();

    const evidence = await finalize();

    // Backend interactions were observable (at least one call) and none failed.
    const result = makeResult(
      evidence,
      (e) => e.network.length > 0 && e.network.every((n) => n.status < 500),
      "Coverage interactions produced observable, non-erroring backend calls.",
    );
    expect(result.outcome, JSON.stringify(result.evidence, null, 2)).toBe("pass");
  });
});
