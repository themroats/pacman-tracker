/**
 * API client tests — verify request construction, auth headers, and error handling.
 *
 * Tests:
 * - Auth header attached when token exists
 * - No auth header when token absent
 * - Successful JSON response parsed
 * - Error response throws ApiClientError
 * - Query string built correctly
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// We need to mock fetch before importing the client
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

// Mock import.meta.env
vi.stubGlobal("import", { meta: { env: { VITE_API_URL: "http://test:8000/api/v1" } } });

describe("API Client", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("attaches Authorization header when token exists", async () => {
    localStorage.setItem("access_token", "test-token-123");
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ cities: [] }),
    });

    const { citiesApi } = await import("@/api/client");
    await citiesApi.list();

    const [url, init] = mockFetch.mock.calls[0];
    expect(init.headers).toHaveProperty("Authorization", "Bearer test-token-123");
  });

  it("omits Authorization header when no token", async () => {
    localStorage.removeItem("access_token");
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ cities: [] }),
    });

    const { citiesApi } = await import("@/api/client");
    await citiesApi.list();

    const [url, init] = mockFetch.mock.calls[0];
    expect(init.headers.Authorization).toBeUndefined();
  });

  it("parses successful JSON response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        cities: [{ id: 1, name: "Seattle", state: "WA" }],
      }),
    });

    const { citiesApi } = await import("@/api/client");
    const result = await citiesApi.list();

    expect(result.cities).toHaveLength(1);
    expect(result.cities[0].name).toBe("Seattle");
  });

  it("throws ApiClientError on error response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({
        error: { code: "NOT_FOUND", message: "City not found", details: {} },
      }),
    });

    const { coverageApi, ApiClientError } = await import("@/api/client");

    await expect(coverageApi.city(9999)).rejects.toThrow();
  });

  it("sends POST with JSON body for route suggest", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        route: null,
        segments: [],
        message: "No route found",
      }),
    });

    const { routesApi } = await import("@/api/client");
    await routesApi.suggest({
      city_id: 1,
      start_lat: 47.61,
      start_lng: -122.33,
      target_distance_m: 3000,
    } as any);

    const [url, init] = mockFetch.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toHaveProperty("city_id", 1);
  });

  it("builds query params for activity filters", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ activities: [], total: 0, page: 1 }),
    });

    const { activitiesApi } = await import("@/api/client");
    await activitiesApi.list({ sport_type: "Run", limit: 10 } as any);

    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain("sport_type=Run");
    expect(url).toContain("limit=10");
  });
});
