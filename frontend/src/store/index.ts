/**
 * Zustand store — centralised application state.
 *
 * Slices: auth, activities, coverage, routes, progress, ui
 */

import { create } from "zustand";
import type {
  ActivityFilters,
  ActivitySummary,
  CityListItem,
  GeoJSONFeatureCollection,
  NeighborhoodCoverage,
  NeighborhoodListItem,
  SyncStatusResponse,
} from "@/types/api";

// ---------------------------------------------------------------------------
// State shape
// ---------------------------------------------------------------------------

export interface AuthSlice {
  isAuthenticated: boolean;
  userId: number | null;
  displayName: string | null;
  accessToken: string | null;
  syncStatus: string | null;
}

export interface ActivitySlice {
  activities: ActivitySummary[];
  activitiesGeoJSON: GeoJSONFeatureCollection | null;
  filters: ActivityFilters;
  totalActivities: number;
  currentPage: number;
}

export interface CoverageSlice {
  selectedCityId: number | null;
  selectedNeighborhoodId: number | null;
  neighborhoodCoverages: NeighborhoodCoverage[];
  cityCoveragePercentage: number | null;
}

export interface UISlice {
  isLoading: boolean;
  error: string | null;
  syncStatus: SyncStatusResponse | null;
}

export interface CitySlice {
  cities: CityListItem[];
  neighborhoods: NeighborhoodListItem[];
}

export interface AppState
  extends AuthSlice,
    ActivitySlice,
    CoverageSlice,
    UISlice,
    CitySlice {
  // Auth actions
  login: (userId: number, displayName: string, accessToken: string) => void;
  logout: () => void;

  // Activity actions
  setActivities: (activities: ActivitySummary[], total: number) => void;
  setActivitiesGeoJSON: (geojson: GeoJSONFeatureCollection) => void;
  setFilters: (filters: Partial<ActivityFilters>) => void;
  setPage: (page: number) => void;

  // Coverage actions
  setSelectedCity: (cityId: number | null) => void;
  setSelectedNeighborhood: (neighborhoodId: number | null) => void;
  setNeighborhoodCoverages: (coverages: NeighborhoodCoverage[]) => void;
  setCityCoveragePercentage: (pct: number | null) => void;

  // City actions
  setCities: (cities: CityListItem[]) => void;
  setNeighborhoods: (neighborhoods: NeighborhoodListItem[]) => void;

  // UI actions
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setSyncStatus: (status: SyncStatusResponse | null) => void;
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useAppStore = create<AppState>((set) => ({
  // --- Auth ---
  isAuthenticated: !!localStorage.getItem("access_token"),
  userId: null,
  displayName: null,
  accessToken: localStorage.getItem("access_token"),
  syncStatus: null,

  login: (userId, displayName, accessToken) => {
    localStorage.setItem("access_token", accessToken);
    set({ isAuthenticated: true, userId, displayName, accessToken });
  },

  logout: () => {
    localStorage.removeItem("access_token");
    set({
      isAuthenticated: false,
      userId: null,
      displayName: null,
      accessToken: null,
      syncStatus: null,
    });
  },

  // --- Activities ---
  activities: [],
  activitiesGeoJSON: null,
  filters: {},
  totalActivities: 0,
  currentPage: 1,

  setActivities: (activities, total) => set({ activities, totalActivities: total }),
  setActivitiesGeoJSON: (geojson) => set({ activitiesGeoJSON: geojson }),
  setFilters: (filters) =>
    set((state) => ({ filters: { ...state.filters, ...filters }, currentPage: 1 })),
  setPage: (page) => set({ currentPage: page }),

  // --- Coverage ---
  selectedCityId: null,
  selectedNeighborhoodId: null,
  neighborhoodCoverages: [],
  cityCoveragePercentage: null,

  setSelectedCity: (cityId) =>
    set({ selectedCityId: cityId, selectedNeighborhoodId: null }),
  setSelectedNeighborhood: (neighborhoodId) =>
    set({ selectedNeighborhoodId: neighborhoodId }),
  setNeighborhoodCoverages: (coverages) => set({ neighborhoodCoverages: coverages }),
  setCityCoveragePercentage: (pct) => set({ cityCoveragePercentage: pct }),

  // --- Cities ---
  cities: [],
  neighborhoods: [],

  setCities: (cities) => set({ cities }),
  setNeighborhoods: (neighborhoods) => set({ neighborhoods }),

  // --- UI ---
  isLoading: false,
  error: null,

  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  setSyncStatus: (status) => set({ syncStatus: status }),
}));
