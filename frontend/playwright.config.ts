import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright configuration for the local browser-based verification harness
 * (feature 008-browser-verification-harness).
 *
 * The harness drives the running frontend (started by infra/verify-up.ps1) in a
 * real browser to confirm fixes before pushing, using the dev auth bypass and a
 * seeded demo user. It is LOCAL-ONLY and never run in CI.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  // Each spec is an on-demand verification; fail fast and don't retry by default.
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.VERIFY_BASE_URL ?? "http://localhost:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
  projects: [
    {
      name: "headless",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "headed",
      use: { ...devices["Desktop Chrome"], headless: false },
    },
  ],
});
