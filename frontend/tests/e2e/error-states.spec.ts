import { test, expect } from "@playwright/test";
import { seedAuth } from "./helpers/auth";
import { forceResponse, ErrorPresets } from "./helpers/intercept";
import { startEvidence, makeResult } from "./helpers/evidence";

/**
 * Verify error-state and edge-case UX deterministically.
 *
 * Forces backend responses at the browser/network layer so error UI appears
 * reliably without changing the real backend. Prerequisites: the warm
 * verification stack is running (infra/verify-up.ps1).
 */

test.describe("error-state UX", () => {
  test.beforeEach(async ({ page }) => {
    await seedAuth(page);
  });

  test("session expired (401) surfaces a user-facing error", async ({ page }) => {
    const finalize = startEvidence(page);

    // Force every coverage/cities API call to fail with 401.
    await forceResponse(page, ErrorPresets.sessionExpired("**/api/v1/**"));
    await page.goto("/coverage");

    // The global error handler raises an alert toast with the message.
    const alert = page.getByRole("alert");
    await expect(alert.first()).toBeVisible();
    await expect(alert.first()).toContainText(/session has expired|sign in/i);

    const evidence = await finalize();
    const result = makeResult(
      evidence,
      (e) => e.network.some((n) => n.status === 401),
      "Expected 401 session-expired UI appeared.",
    );
    expect(result.outcome, JSON.stringify(result.evidence, null, 2)).toBe("pass");
  });

  test("routing unavailable (503) shows the routing-unavailable path", async ({ page }) => {
    // The RoutePage decides availability from /health's osrm_available flag.
    await page.route("**/health", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", osrm_available: false }),
      });
    });

    await page.goto("/route");

    // The UI clearly reflects the "routing unavailable" path, not a real route.
    await expect(page.getByText(/route suggestions unavailable/i)).toBeVisible();
    await expect(page.getByText(/routing service is not running/i)).toBeVisible();
  });

  test("not found / empty (404) is handled without an unexpected crash", async ({ page }) => {
    const finalize = startEvidence(page);

    // The coverage data call only fires once a city is selected, so force a 404
    // on the city coverage endpoint, then drive the selection that triggers it.
    await forceResponse(page, ErrorPresets.notFound("**/api/v1/coverage/city/**"));
    await page.goto("/coverage");

    // Selecting a city issues coverageApi.city(cityId) -> /coverage/city/{id}.
    await page.getByLabel("City").selectOption({ label: "Seattle, Washington" });

    // The global error handler surfaces the failure as an alert toast rather
    // than white-screening, and we stay on /coverage.
    await expect(page.getByRole("alert").first()).toBeVisible();
    await expect(page).toHaveURL(/\/coverage$/);

    const evidence = await finalize();
    const result = makeResult(
      evidence,
      // Expected: a 404 was observed AND the app did not throw an unhandled error.
      (e) =>
        e.network.some((n) => n.status === 404) &&
        !e.consoleErrors.some((m) => /uncaught|cannot read/i.test(m)),
      "Expected not-found UI appeared without an unexpected crash.",
    );
    expect(result.outcome, JSON.stringify(result.evidence, null, 2)).toBe(
      result.expected ? "pass" : "fail",
    );
    // Distinguish expected error UI from an unexpected failure.
    expect(result.expected).toBe(true);
  });
});
