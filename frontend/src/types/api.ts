/**
 * TypeScript type definitions matching API contracts.
 * See: specs/001-strava-street-mapper/contracts/api.md
 */

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface AuthCallbackResponse {
  user_id: number;
  display_name: string;
  access_token: string;
  home_city: number | null;
  sync_status: string;
}

export interface LogoutResponse {
  message: string;
}

// ---------------------------------------------------------------------------
// User
// ---------------------------------------------------------------------------

export interface UserResponse {
  user_id: number;
  display_name: string;
  profile_image_url: string | null;
  home_city: number | null;
  sync_status: string;
}

// ---------------------------------------------------------------------------
// Activities
// ---------------------------------------------------------------------------

export interface ActivitySummary {
  id: number;
  strava_activity_id: number;
  name: string;
  sport_type: string;
  start_date: string;
  distance_meters: number;
  duration_seconds: number;
  moving_time_seconds: number;
  pace_min_per_km: number;
  has_gps: boolean;
  is_on_street: boolean;
  city_name: string | null;
}

export interface ActivityDetail extends ActivitySummary {
  gps_trace: GeoJSONLineString | null;
}

export interface ActivityListResponse {
  activities: ActivitySummary[];
  total: number;
  page: number;
  per_page: number;
}

export interface ActivityFilters {
  sport_type?: string;
  start_date?: string;
  end_date?: string;
  min_distance?: number;
  max_distance?: number;
  city_id?: number;
  page?: number;
  per_page?: number;
}

// ---------------------------------------------------------------------------
// Sync
// ---------------------------------------------------------------------------

export interface SyncStatusResponse {
  status: string;
  total_activities: number;
  imported_activities: number;
  matched_activities: number;
  last_sync_at: string | null;
  error_message: string | null;
}

export interface SyncTriggerResponse {
  message: string;
  status: string;
}

// ---------------------------------------------------------------------------
// Coverage
// ---------------------------------------------------------------------------

export interface CityCoverageResponse {
  city: {
    id: number;
    name: string;
    coverage_percentage: number;
    streets_traveled: number;
    streets_total: number;
    distance_traveled_m: number;
    distance_total_m: number;
  };
  neighborhoods: NeighborhoodCoverage[];
}

export interface NeighborhoodCoverage {
  id: number;
  name: string;
  coverage_percentage: number;
  streets_traveled: number;
  streets_total: number;
  distance_traveled_m: number;
  distance_total_m: number;
}

export interface NeighborhoodDetailResponse {
  neighborhood: {
    id: number;
    name: string;
    city_name: string;
    coverage_percentage: number;
    streets_traveled: number;
    streets_total: number;
  };
  boundary: GeoJSONPolygon;
}

// ---------------------------------------------------------------------------
// Routes
// ---------------------------------------------------------------------------

export interface RouteSuggestRequest {
  start_point: { lng: number; lat: number };
  distance_meters: number;
  city_id: number;
  neighborhood_id?: number;
  variation?: number;
  preferences?: RoutePreferences;
}

export interface RoutePreferences {
  residential: number;
  main_roads: number;
  trails: number;
  other: number;
}

export interface RouteSuggestResponse {
  route: {
    id: number;
    distance_meters: number;
    estimated_duration_seconds: number;
    untraveled_distance_meters: number;
    untraveled_ratio: number;
    geometry: GeoJSONLineString;
  } | null;
  segments?: RouteSegment[];
  message?: string;
  suggested_neighborhoods?: { id: number; name: string; coverage_percentage: number }[];
}

export interface RouteSegment {
  street_name: string;
  is_untraveled: boolean;
  length_meters: number;
  geometry?: GeoJSONLineString;
}

export interface RouteHistoryItem {
  id: number;
  created_at: string;
  distance_meters: number;
  untraveled_ratio: number;
  neighborhood_name: string | null;
  city_name: string;
}

// ---------------------------------------------------------------------------
// Progress
// ---------------------------------------------------------------------------

export interface ProgressResponse {
  city_name: string;
  current_coverage_percentage: number;
  milestones: Milestone[];
  timeline: TimelineEntry[];
}

export interface Milestone {
  label: string;
  neighborhood_name: string;
  reached: boolean;
  date: string | null;
}

export interface TimelineEntry {
  date: string;
  coverage_percentage: number;
  streets_traveled: number;
}

export interface OverallStatsResponse {
  total_activities: number;
  total_distance_meters: number;
  total_unique_streets: number;
  cities: {
    city_name: string;
    coverage_percentage: number;
    streets_traveled: number;
    streets_total: number;
  }[];
}

// ---------------------------------------------------------------------------
// Cities
// ---------------------------------------------------------------------------

export interface CityListItem {
  id: number;
  name: string;
  state: string;
  total_street_segments: number;
  total_neighborhoods: number;
}

export interface CityListResponse {
  cities: CityListItem[];
  bootstrap_status?: "idle" | "loading" | "ready" | "failed";
  bootstrap_error?: string | null;
}

export interface NeighborhoodListItem {
  id: number;
  name: string;
  total_street_segments: number;
  coverage_percentage: number;
}

export interface NeighborhoodBoundaryProperties {
  id: number;
  name: string;
  coverage_percentage: number;
}

// ---------------------------------------------------------------------------
// GeoJSON primitives
// ---------------------------------------------------------------------------

export interface GeoJSONLineString {
  type: "LineString";
  coordinates: [number, number][];
}

export interface GeoJSONPolygon {
  type: "Polygon";
  coordinates: [number, number][][];
}

export interface GeoJSONFeature<G = GeoJSONLineString, P = Record<string, unknown>> {
  type: "Feature";
  properties: P;
  geometry: G;
}

export interface GeoJSONFeatureCollection<
  G = GeoJSONLineString,
  P = Record<string, unknown>,
> {
  type: "FeatureCollection";
  features: GeoJSONFeature<G, P>[];
}

export type NeighborhoodBoundaryFeatureCollection = GeoJSONFeatureCollection<
  GeoJSONPolygon,
  NeighborhoodBoundaryProperties
>;

// ---------------------------------------------------------------------------
// Webhook (server-only, typed for reference)
// ---------------------------------------------------------------------------

export interface StravaWebhookEvent {
  aspect_type: "create" | "update" | "delete";
  event_time: number;
  object_id: number;
  object_type: string;
  owner_id: number;
  subscription_id: number;
  updates: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Start Points
// ---------------------------------------------------------------------------

export interface SavedStartPoint {
  id: number;
  name: string;
  lng: number;
  lat: number;
  is_default: boolean;
}

export interface StartPointCreate {
  name: string;
  lng: number;
  lat: number;
  is_default: boolean;
}

// ---------------------------------------------------------------------------
// Coverage Plans
// ---------------------------------------------------------------------------

export interface CoveragePlanCreate {
  neighborhood_id: number;
  city_id: number;
  preferred_route_distance_m: number;
  start_point_id: number;
  variation?: number;
}

export interface CoveragePlanRouteInfo {
  sequence_order: number;
  status: string;
  route_id: number;
  distance_meters: number;
  estimated_duration_seconds: number;
  streets_targeted: number;
  untraveled_ratio: number;
}

export interface CoveragePlanResponse {
  id: number;
  neighborhood_id: number;
  neighborhood_name: string;
  city_id: number;
  status: string;
  preferred_route_distance_m: number;
  initial_coverage_pct: number;
  target_coverage_pct: number;
  total_routes: number;
  total_distance_m: number;
  error_message: string | null;
  routes: CoveragePlanRouteInfo[];
}

export interface CoveragePlanSummary {
  id: number;
  neighborhood_name: string;
  status: string;
  total_routes: number;
  total_distance_m: number;
  initial_coverage_pct: number;
  goal_id: number | null;
}

// ---------------------------------------------------------------------------
// Coverage Goals
// ---------------------------------------------------------------------------

export interface CoverageGoalCreate {
  city_id: number;
  target_coverage_pct: number;
  preferred_route_distance_m: number;
}

export interface GoalNeighborhoodInfo {
  neighborhood_id: number;
  neighborhood_name: string;
  current_coverage_pct: number;
  untraveled_streets: number;
  untraveled_distance_m: number;
  plan_id: number | null;
  plan_status: string | null;
  estimated_routes: number;
}

export interface CoverageGoalResponse {
  id: number;
  city_id: number;
  target_coverage_pct: number;
  current_coverage_pct: number;
  status: string;
  total_routes: number;
  total_distance_m: number;
  neighborhoods: GoalNeighborhoodInfo[];
}

export interface CoverageGoalSummary {
  id: number;
  city_id: number;
  target_coverage_pct: number;
  current_coverage_pct: number;
  status: string;
  total_neighborhoods: number;
  total_routes: number;
}

// ---------------------------------------------------------------------------
// Error
// ---------------------------------------------------------------------------

export interface ApiError {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
}
