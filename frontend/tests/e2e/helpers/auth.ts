import type { Page } from "@playwright/test";

/**
 * Authenticated-session seeding for the verification harness (feature 008).
 *
 * The frontend persists auth in localStorage and treats the presence of an
 * `access_token` as "logged in" (see frontend/src/store/index.ts). Seeding these
 * keys before navigation lets the harness land directly on protected pages
 * without completing real Strava OAuth — the backend runs with DEV_AUTH_BYPASS
 * and resolves the request to the seeded demo user.
 */

export interface DemoAuth {
  /** Placeholder token; the backend bypass ignores it server-side. */
  accessToken: string;
  /** Demo user id — matches the single seeded user in the verification DB. */
  userId: number;
  /** Display name shown in the UI. */
  displayName: string;
}

export const DEFAULT_DEMO_AUTH: DemoAuth = {
  accessToken: "verification-harness-demo-token",
  userId: 1,
  displayName: "Demo Runner",
};

/**
 * Seed the frontend auth state into localStorage BEFORE navigation.
 *
 * Keys MUST match the app store exactly:
 *   - access_token : string
 *   - user_id      : JSON-stringified number
 *   - display_name : string
 */
export async function seedAuth(page: Page, auth: Partial<DemoAuth> = {}): Promise<void> {
  const resolved: DemoAuth = { ...DEFAULT_DEMO_AUTH, ...auth };

  // addInitScript runs before any page script on every navigation, so the
  // store reads the seeded values on first load and never redirects to login.
  await page.addInitScript((a: DemoAuth) => {
    window.localStorage.setItem("access_token", a.accessToken);
    window.localStorage.setItem("user_id", JSON.stringify(a.userId));
    window.localStorage.setItem("display_name", a.displayName);
  }, resolved);
}

/** Clear the seeded auth state (e.g., to verify the unauthenticated redirect). */
export async function clearAuth(page: Page): Promise<void> {
  await page.addInitScript(() => {
    window.localStorage.removeItem("access_token");
    window.localStorage.removeItem("user_id");
    window.localStorage.removeItem("display_name");
  });
}
