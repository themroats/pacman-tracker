/**
 * Integration tests for API error → toast notification pipeline (SC-001).
 *
 * Verifies:
 * - ApiClientError from a failed request triggers the global onError handler
 * - The global handler calls addToast with the error message
 * - Non-JSON error responses are handled gracefully
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

describe("API Error → Toast Pipeline", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    localStorage.clear();
    // Reset module cache so setApiErrorHandler re-registers
    vi.resetModules();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("calls global onError handler when API returns structured error", async () => {
    const errorHandler = vi.fn();

    const { setApiErrorHandler, citiesApi, ApiClientError } = await import(
      "@/api/client"
    );
    setApiErrorHandler(errorHandler);

    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({
        error: {
          code: "INTERNAL_ERROR",
          message: "Something went wrong",
          details: {},
        },
      }),
    });

    await expect(citiesApi.list()).rejects.toThrow();

    expect(errorHandler).toHaveBeenCalledTimes(1);
    const err = errorHandler.mock.calls[0][0];
    expect(err).toBeInstanceOf(ApiClientError);
    expect(err.message).toBe("Something went wrong");
    expect(err.code).toBe("INTERNAL_ERROR");
    expect(err.status).toBe(500);
  });

  it("calls global onError handler on non-JSON error response", async () => {
    const errorHandler = vi.fn();

    const { setApiErrorHandler, citiesApi } = await import("@/api/client");
    setApiErrorHandler(errorHandler);

    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 502,
      statusText: "Bad Gateway",
      json: async () => {
        throw new Error("not JSON");
      },
    });

    await expect(citiesApi.list()).rejects.toThrow();

    expect(errorHandler).toHaveBeenCalledTimes(1);
    const err = errorHandler.mock.calls[0][0];
    expect(err.code).toBe("UNKNOWN");
    expect(err.message).toBe("Bad Gateway");
    expect(err.status).toBe(502);
  });

  it("does not call onError handler on successful response", async () => {
    const errorHandler = vi.fn();

    const { setApiErrorHandler, citiesApi } = await import("@/api/client");
    setApiErrorHandler(errorHandler);

    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        cities: [],
        bootstrap_status: "idle",
        bootstrap_error: null,
      }),
    });

    await citiesApi.list();

    expect(errorHandler).not.toHaveBeenCalled();
  });

  it("propagates 401 UNAUTHORIZED with correct error code", async () => {
    const errorHandler = vi.fn();

    const { setApiErrorHandler, activitiesApi } = await import("@/api/client");
    setApiErrorHandler(errorHandler);

    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({
        error: {
          code: "UNAUTHORIZED",
          message: "Missing authorization header",
          details: {},
        },
      }),
    });

    await expect(activitiesApi.list()).rejects.toThrow();

    expect(errorHandler).toHaveBeenCalledTimes(1);
    const err = errorHandler.mock.calls[0][0];
    expect(err.code).toBe("UNAUTHORIZED");
    expect(err.status).toBe(401);
  });

  it("propagates OSRM_UNAVAILABLE error code", async () => {
    const errorHandler = vi.fn();

    const { setApiErrorHandler, routesApi } = await import("@/api/client");
    setApiErrorHandler(errorHandler);

    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 503,
      json: async () => ({
        error: {
          code: "OSRM_UNAVAILABLE",
          message: "Route suggestions are temporarily unavailable",
          details: {},
        },
      }),
    });

    await expect(
      routesApi.suggest({
        start_point: { lng: -122.33, lat: 47.6 },
        distance_meters: 5000,
        city_id: 1,
      } as any)
    ).rejects.toThrow();

    expect(errorHandler).toHaveBeenCalledTimes(1);
    const err = errorHandler.mock.calls[0][0];
    expect(err.code).toBe("OSRM_UNAVAILABLE");
    expect(err.status).toBe(503);
  });
});
