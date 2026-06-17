import type { Page, Route } from "@playwright/test";

/**
 * Browser/network-layer response forcing for the verification harness (feature 008).
 *
 * These helpers intercept HTTP requests in the browser using Playwright's route
 * API and fulfill them with a synthetic status/body. The real backend is NEVER
 * contacted for a forced request, so error-state UI can be reproduced
 * deterministically without any backend changes (FR-008).
 */

export interface ForcedResponse {
  /** Glob pattern for requests to intercept, e.g. "**\/api/v1/route**". */
  urlPattern: string;
  /** Synthetic HTTP status to return (e.g. 401, 503, 404). */
  status: number;
  /** Optional JSON body matching the endpoint's response shape. */
  body?: unknown;
}

/**
 * Install a browser-layer route handler that fulfills matching requests with the
 * synthetic response. Call before the action that triggers the request.
 */
export async function forceResponse(page: Page, scenario: ForcedResponse): Promise<void> {
  await page.route(scenario.urlPattern, async (route: Route) => {
    await route.fulfill({
      status: scenario.status,
      contentType: "application/json",
      body: JSON.stringify(scenario.body ?? {}),
    });
  });
}

/** Remove a previously installed forced-response handler. */
export async function clearForcedResponse(page: Page, urlPattern: string): Promise<void> {
  await page.unroute(urlPattern);
}

/**
 * Presets for the three priority error states (SC-004). Each returns a
 * {@link ForcedResponse} for a given URL pattern. Bodies use the app's error
 * envelope ({ error: { code, message, details } }) so the frontend surfaces the
 * message via its global error handler.
 */
export const ErrorPresets = {
  /** 401 — session expired / authorization failure. */
  sessionExpired(urlPattern: string): ForcedResponse {
    return {
      urlPattern,
      status: 401,
      body: {
        error: {
          code: "UNAUTHORIZED",
          message: "Your session has expired. Please sign in again.",
          details: {},
        },
      },
    };
  },
  /** 503 — routing/service unavailable. */
  routingUnavailable(urlPattern: string): ForcedResponse {
    return {
      urlPattern,
      status: 503,
      body: {
        error: {
          code: "SERVICE_UNAVAILABLE",
          message: "Routing service unavailable.",
          details: {},
        },
      },
    };
  },
  /** 404 — empty / not found. */
  notFound(urlPattern: string): ForcedResponse {
    return {
      urlPattern,
      status: 404,
      body: {
        error: { code: "NOT_FOUND", message: "Not found.", details: {} },
      },
    };
  },
};
