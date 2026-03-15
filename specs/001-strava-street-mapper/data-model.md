# Data Model: Strava Street Mapper

**Feature**: 001-strava-street-mapper  
**Date**: 2026-02-28  
**Storage**: SQLite + SpatiaLite (local dev) / PostgreSQL + PostGIS (production)

## Entity Relationship Overview

```
User 1──* Activity
User 1──* UserStreetCoverage
User 1──* CoverageSnapshot
User 1──* RouteSuggestion

City 1──* Neighborhood
City 1──* StreetSegment
Neighborhood 1──* StreetSegment (via centroid containment)

Activity *──* StreetSegment (through UserStreetCoverage)
RouteSuggestion *──* StreetSegment (through RouteSuggestionSegment)
```

## Entities

### User

Represents an authenticated Strava user.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | Integer | PK, auto-increment | Internal user ID |
| strava_athlete_id | BigInteger | UNIQUE, NOT NULL | Strava's athlete ID |
| display_name | String(255) | NOT NULL | Athlete's display name from Strava |
| profile_image_url | String(500) | nullable | Strava profile picture URL |
| access_token_encrypted | Text | NOT NULL | Encrypted Strava OAuth access token |
| refresh_token_encrypted | Text | NOT NULL | Encrypted Strava OAuth refresh token |
| token_expires_at | DateTime | NOT NULL | Access token expiration timestamp |
| strava_scope | String(100) | NOT NULL | Granted OAuth scopes |
| home_city_id | Integer | FK → City.id, nullable | User's selected home city |
| last_sync_at | DateTime | nullable | Last successful activity sync timestamp |
| sync_status | String(20) | NOT NULL, default "idle" | "idle", "importing", "syncing", "error" |
| created_at | DateTime | NOT NULL, default now | Account creation timestamp |
| updated_at | DateTime | NOT NULL, auto-update | Last modification timestamp |

**Validation rules**:
- `strava_athlete_id` must be positive
- `sync_status` must be one of: "idle", "importing", "syncing", "error", "revoked"
- `token_expires_at` must be in the future when tokens are refreshed

---

### Activity

A single exercise session imported from Strava.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | Integer | PK, auto-increment | Internal activity ID |
| user_id | Integer | FK → User.id, NOT NULL | Owning user |
| strava_activity_id | BigInteger | UNIQUE, NOT NULL | Strava's activity ID |
| name | String(255) | NOT NULL | Activity title from Strava |
| sport_type | String(50) | NOT NULL | "Run", "Walk", "Ride", etc. |
| start_date | DateTime | NOT NULL | Activity start time (UTC) |
| distance_meters | Float | NOT NULL | Total distance in meters |
| duration_seconds | Integer | NOT NULL | Elapsed time in seconds |
| moving_time_seconds | Integer | NOT NULL | Moving time in seconds |
| summary_polyline | Text | nullable | Google-encoded summary polyline |
| detailed_polyline | Text | nullable | Google-encoded detailed polyline |
| gps_trace | Geometry(LineString, 4326) | nullable | Full GPS trace as WGS84 LineString |
| has_gps | Boolean | NOT NULL, default false | Whether activity has GPS data |
| is_on_street | Boolean | NOT NULL, default true | True if activity is on road network |
| import_status | String(20) | NOT NULL, default "pending" | "pending", "polyline_imported", "streams_imported", "matched" |
| city_id | Integer | FK → City.id, nullable | Detected city for this activity |
| created_at | DateTime | NOT NULL, default now | Import timestamp |

**Validation rules**:
- `distance_meters` must be ≥ 0
- `duration_seconds` must be > 0
- `sport_type` must be a recognized Strava sport type
- `import_status` must be one of: "pending", "polyline_imported", "streams_imported", "matched"

**State transitions**:
```
pending → polyline_imported  (Phase A: detailed polyline fetched)
polyline_imported → streams_imported  (Phase B: GPS streams fetched)
streams_imported → matched  (GPS trace matched against street network)
```

---

### City

A top-level geographic boundary for a supported city.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | Integer | PK, auto-increment | Internal city ID |
| name | String(100) | NOT NULL | City display name |
| state | String(50) | NOT NULL | State/region |
| country | String(50) | NOT NULL, default "US" | Country code |
| boundary | Geometry(MultiPolygon, 4326) | NOT NULL | City boundary polygon (WGS84) |
| projected_crs | String(20) | NOT NULL | EPSG code for local projections (e.g., "EPSG:2926") |
| total_street_segments | Integer | NOT NULL, default 0 | Cached count of street segments |
| total_street_length_m | Float | NOT NULL, default 0 | Cached total street length in meters |
| osm_data_updated_at | DateTime | nullable | Last OSM street data refresh |
| created_at | DateTime | NOT NULL, default now | Record creation timestamp |

**Seed data** (launch cities):

| Name | State | Projected CRS |
|------|-------|---------------|
| Seattle | Washington | EPSG:2926 |
| Pittsburgh | Pennsylvania | EPSG:2272 |
| Chicago | Illinois | EPSG:3435 |
| New York | New York | EPSG:2263 |
| San Francisco | California | EPSG:2227 |

---

### Neighborhood

A named geographic area within a city.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | Integer | PK, auto-increment | Internal neighborhood ID |
| city_id | Integer | FK → City.id, NOT NULL | Parent city |
| name | String(200) | NOT NULL | Neighborhood display name |
| boundary | Geometry(MultiPolygon, 4326) | NOT NULL | Neighborhood boundary polygon |
| total_street_segments | Integer | NOT NULL, default 0 | Cached count of street segments |
| total_street_length_m | Float | NOT NULL, default 0 | Cached total street length in meters |
| created_at | DateTime | NOT NULL, default now | Record creation timestamp |

**Validation rules**:
- `(city_id, name)` is UNIQUE — no duplicate neighborhood names within a city

---

### StreetSegment

A section of road/sidewalk from the OpenStreetMap network.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | Integer | PK, auto-increment | Internal segment ID |
| city_id | Integer | FK → City.id, NOT NULL | City this segment belongs to |
| neighborhood_id | Integer | FK → Neighborhood.id, nullable | Assigned neighborhood (via centroid) |
| osm_way_id | BigInteger | NOT NULL | OpenStreetMap way ID |
| osm_node_start | BigInteger | NOT NULL | OSM start node ID |
| osm_node_end | BigInteger | NOT NULL | OSM end node ID |
| name | String(255) | nullable | Street name (may be null for unnamed paths) |
| highway_type | String(50) | NOT NULL | OSM highway tag (e.g., "residential", "footway") |
| geometry | Geometry(LineString, 4326) | NOT NULL | Street segment geometry (WGS84) |
| length_meters | Float | NOT NULL | Segment length in meters (computed in projected CRS) |
| created_at | DateTime | NOT NULL, default now | Import timestamp |

**Validation rules**:
- `length_meters` must be > 0
- `(osm_way_id, osm_node_start, osm_node_end)` should be UNIQUE (deduplicate on import)

**Spatial index**: R-tree on `geometry` column (mandatory for performance)

---

### UserStreetCoverage

Tracks which streets a user has traveled. One row per user per street segment.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | Integer | PK, auto-increment | Internal ID |
| user_id | Integer | FK → User.id, NOT NULL | The user |
| street_segment_id | Integer | FK → StreetSegment.id, NOT NULL | The street segment |
| coverage_ratio | Float | NOT NULL | Fraction of street covered (0.0–1.0) |
| is_traveled | Boolean | NOT NULL, default false | True if coverage_ratio ≥ 0.80 |
| first_traveled_at | DateTime | nullable | Date when threshold was first met |
| last_activity_id | Integer | FK → Activity.id, nullable | Most recent activity that contributed |
| updated_at | DateTime | NOT NULL, auto-update | Last recalculation timestamp |

**Validation rules**:
- `coverage_ratio` must be between 0.0 and 1.0
- `(user_id, street_segment_id)` is UNIQUE — one coverage record per user per street
- `is_traveled` must be `true` when `coverage_ratio >= 0.80`

---

### CoverageSnapshot

A point-in-time record of a user's street coverage for milestone tracking.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | Integer | PK, auto-increment | Internal ID |
| user_id | Integer | FK → User.id, NOT NULL | The user |
| city_id | Integer | FK → City.id, NOT NULL | City for this snapshot |
| neighborhood_id | Integer | FK → Neighborhood.id, nullable | Specific neighborhood (null = city-wide) |
| coverage_percentage | Float | NOT NULL | Coverage % at snapshot time |
| total_streets_traveled | Integer | NOT NULL | Count of traveled streets |
| total_streets | Integer | NOT NULL | Total streets in area |
| is_milestone | Boolean | NOT NULL, default false | True if this represents a milestone (25%, 50%, 75%, 100%) |
| milestone_label | String(50) | nullable | e.g., "25%", "50%", "75%", "100%" |
| snapshot_date | Date | NOT NULL | Date of snapshot |
| created_at | DateTime | NOT NULL, default now | Record creation timestamp |

**Validation rules**:
- `coverage_percentage` must be between 0.0 and 100.0
- `milestone_label` must be one of: "25%", "50%", "75%", "100%" (when `is_milestone` is true)

---

### RouteSuggestion

A generated route for a user.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | Integer | PK, auto-increment | Internal ID |
| user_id | Integer | FK → User.id, NOT NULL | The user who requested the route |
| city_id | Integer | FK → City.id, NOT NULL | City context |
| neighborhood_id | Integer | FK → Neighborhood.id, nullable | Target neighborhood (optional) |
| start_point | Geometry(Point, 4326) | NOT NULL | Route starting location |
| route_geometry | Geometry(LineString, 4326) | NOT NULL | Full route line |
| distance_meters | Float | NOT NULL | Total route distance |
| estimated_duration_seconds | Integer | NOT NULL | Estimated time at walking/running pace |
| requested_distance_meters | Float | NOT NULL | User's requested distance |
| untraveled_distance_meters | Float | NOT NULL | Distance on untraveled streets |
| untraveled_ratio | Float | NOT NULL | Fraction of route on untraveled streets |
| created_at | DateTime | NOT NULL, default now | Generation timestamp |

**Validation rules**:
- `distance_meters` must be > 0
- `untraveled_ratio` must be between 0.0 and 1.0
- `distance_meters` should be within 10% of `requested_distance_meters`

---

### RouteSuggestionSegment

Join table linking route suggestions to the street segments they traverse.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | Integer | PK, auto-increment | Internal ID |
| route_suggestion_id | Integer | FK → RouteSuggestion.id, NOT NULL | Parent route |
| street_segment_id | Integer | FK → StreetSegment.id, NOT NULL | Street segment in route |
| sequence_order | Integer | NOT NULL | Order in route (1-based) |
| is_untraveled | Boolean | NOT NULL | Whether this segment was untraveled at generation time |

## Index Strategy

### Primary lookup indexes
- `User.strava_athlete_id` — OAuth lookup
- `Activity(user_id, start_date)` — activity list with date filtering
- `Activity(user_id, sport_type)` — activity type filtering
- `Activity.strava_activity_id` — deduplication during sync
- `UserStreetCoverage(user_id, street_segment_id)` — coverage lookup (UNIQUE)
- `UserStreetCoverage(user_id, is_traveled)` — coverage dashboard queries
- `StreetSegment(city_id, neighborhood_id)` — per-neighborhood street lists
- `CoverageSnapshot(user_id, city_id, snapshot_date)` — progress timeline

### Spatial indexes (R-tree)
- `StreetSegment.geometry` — GPS trace matching
- `Activity.gps_trace` — spatial queries
- `Neighborhood.boundary` — point-in-polygon for street assignment
- `City.boundary` — activity city detection
