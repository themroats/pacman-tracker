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
  CoverageGoalCreate,
  CoverageGoalResponse,
  CoverageGoalSummary,
  CoveragePlanCreate,
  CoveragePlanResponse,
  CoveragePlanSummary,
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
  SavedStartPoint,
  StartPointCreate,
  SyncTriggerResponse,
  SyncStatusResponse,
} from "@/types/api";

const BASE_URL = import.meta.env.VITE_API_URL || "/api/v1";

// ---------------------------------------------------------------------------
// Global error hook — wired to toast notifications by the store
// ---------------------------------------------------------------------------

let _onApiError: ((error: ApiClientError) => void) | null = null;

/** Register a global callback invoked on every ApiClientError. */
export function setApiErrorHandler(handler: (error: ApiClientError) => void) {
  _onApiError = handler;
}

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
      const err = new ApiClientError(
        { code: "UNKNOWN", message: res.statusText, details: {} },
        res.status,
      );
      _onApiError?.(err);
      throw err;
    }
    const err = new ApiClientError(body.error, res.status);
    _onApiError?.(err);
    throw err;
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

  /** Fetch a route suggestion as a GPX File object. */
  async fetchGpx(routeId: number): Promise<File> {
    const url = `${BASE_URL}/routes/${routeId}/export/gpx`;
    const res = await fetch(url, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error(`GPX export failed: ${res.status}`);
    const blob = await res.blob();
    return new File([blob], `pacman-route-${routeId}.gpx`, {
      type: "application/gpx+xml",
    });
  },

  /** Fetch route geometry as GeoJSON for map display. */
  async geojson(routeId: number): Promise<GeoJSON.Feature> {
    return request<GeoJSON.Feature>(`/routes/${routeId}/geojson`);
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

// ---------------------------------------------------------------------------
// Start Points
// ---------------------------------------------------------------------------

export const startPointsApi = {
  /** List saved start points. */
  async list(): Promise<SavedStartPoint[]> {
    return request<SavedStartPoint[]>("/start-points");
  },

  /** Save a new start point. */
  async create(body: StartPointCreate): Promise<SavedStartPoint> {
    return request<SavedStartPoint>("/start-points", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  /** Update a start point. */
  async update(
    id: number,
    body: { name?: string; is_default?: boolean },
  ): Promise<SavedStartPoint> {
    return request<SavedStartPoint>(`/start-points/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  },

  /** Delete a start point. */
  async remove(id: number): Promise<void> {
    return request<void>(`/start-points/${id}`, { method: "DELETE" });
  },
};

// ---------------------------------------------------------------------------
// Coverage Plans
// ---------------------------------------------------------------------------

export const plansApi = {
  /** List user's coverage plans. */
  async list(): Promise<CoveragePlanSummary[]> {
    return request<CoveragePlanSummary[]>("/plans");
  },

  /** Create a neighborhood coverage plan. */
  async createNeighborhood(body: CoveragePlanCreate): Promise<CoveragePlanResponse> {
    return request<CoveragePlanResponse>("/plans/neighborhood", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  /** Get a plan with its routes. */
  async get(planId: number): Promise<CoveragePlanResponse> {
    return request<CoveragePlanResponse>(`/plans/${planId}`);
  },

  /** Delete a coverage plan. */
  async remove(planId: number): Promise<void> {
    return request<void>(`/plans/${planId}`, { method: "DELETE" });
  },

  /** Fetch a plan route as GPX file. */
  async fetchRouteGpx(routeId: number): Promise<File> {
    return routesApi.fetchGpx(routeId);
  },
};

// ---------------------------------------------------------------------------
// Coverage Goals
// ---------------------------------------------------------------------------

export const goalsApi = {
  /** List user's coverage goals. */
  async list(): Promise<CoverageGoalSummary[]> {
    return request<CoverageGoalSummary[]>("/plans/goals");
  },

  /** Create a city-level coverage goal. */
  async create(body: CoverageGoalCreate): Promise<CoverageGoalResponse> {
    return request<CoverageGoalResponse>("/plans/goals", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  /** Get a goal with its linked plans. */
  async get(goalId: number): Promise<CoverageGoalResponse> {
    return request<CoverageGoalResponse>(`/plans/goals/${goalId}`);
  },
};

export { ApiClientError };
