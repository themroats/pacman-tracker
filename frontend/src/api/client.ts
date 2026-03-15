/**
 * Typed API client with fetch wrappers and error handling.
 */

import type {
  ActivityDetail,
  ActivityFilters,
  ActivityListResponse,
  ApiError,
  AuthCallbackResponse,
  CityCoverageResponse,
  CityListResponse,
  GeoJSONFeatureCollection,
  NeighborhoodBoundaryFeatureCollection,
  LogoutResponse,
  NeighborhoodDetailResponse,
  NeighborhoodListItem,
  OverallStatsResponse,
  ProgressResponse,
  RouteSuggestRequest,
  RouteSuggestResponse,
  RouteHistoryItem,
  SyncTriggerResponse,
  SyncStatusResponse,
} from "@/types/api";

const BASE_URL = import.meta.env.VITE_API_URL || "/api/v1";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

class ApiClientError extends Error {
  code: string;
  status: number;
  details: Record<string, unknown>;

  constructor(err: ApiError["error"], status: number) {
    super(err.message);
    this.code = err.code;
    this.status = status;
    this.details = err.details;
  }
}

function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
      ...init?.headers,
    },
  });

  if (!res.ok) {
    let body: ApiError;
    try {
      body = await res.json();
    } catch {
      throw new ApiClientError(
        { code: "UNKNOWN", message: res.statusText, details: {} },
        res.status,
      );
    }
    throw new ApiClientError(body.error, res.status);
  }

  // 204 No Content
  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

function buildQuery(params: Record<string, string | number | boolean | undefined>): string {
  const qs = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join("&");
  return qs ? `?${qs}` : "";
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export const authApi = {
  /** Get Strava login redirect URL. */
  getLoginUrl(): string {
    return `${BASE_URL}/auth/strava`;
  },

  /** Exchange OAuth code for session. */
  async callback(code: string, scope: string, state: string): Promise<AuthCallbackResponse> {
    const res = await fetch(
      `${BASE_URL}/auth/strava/callback${buildQuery({ code, scope, state })}`,
      {
        method: "GET",
      },
    );

    if (!res.ok) {
      let body: ApiError;
      try {
        body = await res.json();
      } catch {
        throw new ApiClientError(
          { code: "UNKNOWN", message: res.statusText, details: {} },
          res.status,
        );
      }
      throw new ApiClientError(body.error, res.status);
    }

    return res.json() as Promise<AuthCallbackResponse>;
  },

  /** Logout current user. */
  async logout(): Promise<LogoutResponse> {
    return request<LogoutResponse>("/auth/logout", { method: "POST" });
  },
};

// ---------------------------------------------------------------------------
// Activities
// ---------------------------------------------------------------------------

export const activitiesApi = {
  /** List activities with optional filters. */
  async list(filters?: ActivityFilters): Promise<ActivityListResponse> {
    const qs = filters ? buildQuery(filters as Record<string, string | number | undefined>) : "";
    return request<ActivityListResponse>(`/activities${qs}`);
  },

  /** Get single activity detail. */
  async get(id: number): Promise<ActivityDetail> {
    return request<ActivityDetail>(`/activities/${id}`);
  },

  /** Get single activity as GeoJSON. */
  async getGeoJSON(id: number): Promise<GeoJSONFeatureCollection> {
    return request<GeoJSONFeatureCollection>(`/activities/${id}/geojson`);
  },

  /** Get all activities as GeoJSON FeatureCollection. */
  async getAllGeoJSON(filters?: ActivityFilters): Promise<GeoJSONFeatureCollection> {
    const qs = filters ? buildQuery(filters as Record<string, string | number | undefined>) : "";
    return request<GeoJSONFeatureCollection>(`/activities/geojson${qs}`);
  },
};

// ---------------------------------------------------------------------------
// Sync
// ---------------------------------------------------------------------------

export const syncApi = {
  /** Get current sync status. */
  async status(): Promise<SyncStatusResponse> {
    return request<SyncStatusResponse>("/sync/status");
  },

  /** Trigger an incremental sync. */
  async trigger(): Promise<SyncTriggerResponse> {
    return request<SyncTriggerResponse>("/sync/trigger", { method: "POST" });
  },

  /** Trigger coverage matching for imported activities. */
  async triggerCoverage(): Promise<SyncTriggerResponse> {
    return request<SyncTriggerResponse>("/sync/coverage", { method: "POST" });
  },
};

// ---------------------------------------------------------------------------
// Coverage
// ---------------------------------------------------------------------------

export const coverageApi = {
  /** City-wide coverage summary. */
  async city(cityId: number): Promise<CityCoverageResponse> {
    return request<CityCoverageResponse>(`/coverage/city/${cityId}`);
  },

  /** Neighborhood coverage detail. */
  async neighborhood(neighborhoodId: number): Promise<NeighborhoodDetailResponse> {
    return request<NeighborhoodDetailResponse>(`/coverage/neighborhood/${neighborhoodId}`);
  },

  /** Neighborhood streets as GeoJSON. */
  async neighborhoodStreets(neighborhoodId: number): Promise<GeoJSONFeatureCollection> {
    return request<GeoJSONFeatureCollection>(
      `/coverage/neighborhood/${neighborhoodId}/streets`,
    );
  },

  /** City streets as GeoJSON with optional filters. */
  async cityStreets(
    cityId: number,
    opts?: { neighborhood_id?: number; status?: string; bbox?: string },
  ): Promise<GeoJSONFeatureCollection> {
    const qs = opts ? buildQuery(opts) : "";
    return request<GeoJSONFeatureCollection>(`/coverage/city/${cityId}/streets${qs}`);
  },
};

// ---------------------------------------------------------------------------
// Routes
// ---------------------------------------------------------------------------

export const routesApi = {
  /** Suggest a new route. */
  async suggest(body: RouteSuggestRequest): Promise<RouteSuggestResponse> {
    return request<RouteSuggestResponse>("/routes/suggest", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  /** Route suggestion history. */
  async history(): Promise<{ routes: RouteHistoryItem[] }> {
    return request<{ routes: RouteHistoryItem[] }>("/routes/history");
  },
};

// ---------------------------------------------------------------------------
// Progress
// ---------------------------------------------------------------------------

export const progressApi = {
  /** Progress timeline for a city. */
  async city(cityId: number): Promise<ProgressResponse> {
    return request<ProgressResponse>(`/progress/city/${cityId}`);
  },

  /** Overall user stats. */
  async stats(): Promise<OverallStatsResponse> {
    return request<OverallStatsResponse>("/progress/stats");
  },
};

// ---------------------------------------------------------------------------
// Cities
// ---------------------------------------------------------------------------

export const citiesApi = {
  /** List all supported cities. */
  async list(): Promise<CityListResponse> {
    return request<CityListResponse>("/cities");
  },

  /** Neighborhoods for a city. */
  async neighborhoods(cityId: number): Promise<{ neighborhoods: NeighborhoodListItem[] }> {
    return request<{ neighborhoods: NeighborhoodListItem[] }>(
      `/cities/${cityId}/neighborhoods`,
    );
  },

  /** Neighborhood boundaries for a city as GeoJSON. */
  async neighborhoodBoundaries(
    cityId: number,
  ): Promise<NeighborhoodBoundaryFeatureCollection> {
    return request<NeighborhoodBoundaryFeatureCollection>(
      `/cities/${cityId}/neighborhoods/boundaries`,
    );
  },

  /** Neighborhood boundary as GeoJSON. */
  async neighborhoodBoundary(
    cityId: number,
    neighborhoodId: number,
  ): Promise<GeoJSONFeatureCollection> {
    return request<GeoJSONFeatureCollection>(
      `/cities/${cityId}/neighborhoods/${neighborhoodId}/boundary`,
    );
  },
};

export { ApiClientError };
