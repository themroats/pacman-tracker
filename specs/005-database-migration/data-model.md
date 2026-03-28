# Data Model: Database Migration — SQLite to PostgreSQL

**Feature**: 005-database-migration  
**Date**: 2026-03-23

## Entity Overview

No new entities are introduced. All existing entities are preserved with PostgreSQL/PostGIS-native types replacing SQLite/SpatiaLite equivalents.

## Entity Definitions

### User

| Field | Type (PostgreSQL) | Constraints | Notes |
|-------|-------------------|-------------|-------|
| id | SERIAL | PK, auto-increment | |
| strava_athlete_id | BIGINT | UNIQUE, NOT NULL | |
| display_name | VARCHAR(255) | NOT NULL | |
| profile_image_url | VARCHAR(500) | nullable | |
| access_token_encrypted | TEXT | NOT NULL | Encrypted Strava OAuth token |
| access_token_hash | VARCHAR(64) | UNIQUE, nullable, indexed | Token lookup index |
| refresh_token_encrypted | TEXT | NOT NULL | |
| token_expires_at | TIMESTAMP | NOT NULL | |
| strava_scope | VARCHAR(100) | NOT NULL | |
| home_city_id | INTEGER | nullable | Soft FK to cities |
| last_sync_at | TIMESTAMP | nullable | |
| sync_started_at | TIMESTAMP | nullable | |
| sync_status | VARCHAR(20) | NOT NULL, default='idle' | Values: idle, importing, syncing, complete, error, revoked |
| created_at | TIMESTAMP | NOT NULL, server_default=now() | |
| updated_at | TIMESTAMP | NOT NULL, server_default=now() | |

**Relationships**: `activities` (1:N)

### Activity

| Field | Type (PostgreSQL) | Constraints | Notes |
|-------|-------------------|-------------|-------|
| id | SERIAL | PK | |
| user_id | INTEGER | FK→users.id, NOT NULL | |
| strava_activity_id | BIGINT | UNIQUE, NOT NULL | |
| name | VARCHAR(255) | NOT NULL | |
| sport_type | VARCHAR(50) | NOT NULL | |
| start_date | TIMESTAMP | NOT NULL | |
| distance_meters | FLOAT | NOT NULL | |
| duration_seconds | INTEGER | NOT NULL | |
| moving_time_seconds | INTEGER | NOT NULL | |
| summary_polyline | TEXT | nullable | Google encoded polyline |
| detailed_polyline | TEXT | nullable | |
| gps_trace | GEOMETRY(LINESTRING, 4326) | nullable | PostGIS geometry column |
| has_gps | BOOLEAN | NOT NULL, default=false | |
| is_on_street | BOOLEAN | NOT NULL, default=true | |
| import_status | VARCHAR(20) | NOT NULL, default='pending' | Values: pending, polyline_imported, streams_imported, matched, error, gps_quality_warning |
| city_id | INTEGER | FK→cities.id, nullable | |
| created_at | TIMESTAMP | NOT NULL, server_default=now() | |

**Indexes**: `ix_activity_user_start_date (user_id, start_date)`, `ix_activity_user_sport_type (user_id, sport_type)`, GiST index on `gps_trace`  
**Relationships**: `user` (N:1)

### City

| Field | Type (PostgreSQL) | Constraints | Notes |
|-------|-------------------|-------------|-------|
| id | SERIAL | PK | |
| name | VARCHAR(100) | NOT NULL | |
| state | VARCHAR(50) | NOT NULL | |
| country | VARCHAR(50) | NOT NULL, default='US' | |
| boundary | GEOMETRY(MULTIPOLYGON, 4326) | NOT NULL | PostGIS geometry column |
| projected_crs | VARCHAR(20) | NOT NULL | e.g., EPSG:2926 |
| total_street_segments | INTEGER | NOT NULL, default=0 | Cached count |
| total_street_length_m | FLOAT | NOT NULL, default=0.0 | Cached sum |
| osm_data_updated_at | TIMESTAMP | nullable | |
| created_at | TIMESTAMP | NOT NULL, server_default=now() | |

**Indexes**: GiST index on `boundary`  
**Relationships**: `neighborhoods` (1:N), `street_segments` (1:N)

### Neighborhood

| Field | Type (PostgreSQL) | Constraints | Notes |
|-------|-------------------|-------------|-------|
| id | SERIAL | PK | |
| city_id | INTEGER | FK→cities.id, NOT NULL | |
| name | VARCHAR(200) | NOT NULL | |
| boundary | GEOMETRY(MULTIPOLYGON, 4326) | NOT NULL | PostGIS geometry column |
| total_street_segments | INTEGER | NOT NULL, default=0 | Cached |
| total_street_length_m | FLOAT | NOT NULL, default=0.0 | Cached |
| created_at | TIMESTAMP | NOT NULL, server_default=now() | |

**Indexes**: UNIQUE (city_id, name), GiST index on `boundary`  
**Relationships**: `city` (N:1), `street_segments` (1:N)

### StreetSegment

| Field | Type (PostgreSQL) | Constraints | Notes |
|-------|-------------------|-------------|-------|
| id | SERIAL | PK | |
| city_id | INTEGER | FK→cities.id, NOT NULL | |
| neighborhood_id | INTEGER | FK→neighborhoods.id, nullable | |
| osm_way_id | BIGINT | NOT NULL | OpenStreetMap way ID |
| osm_node_start | BIGINT | NOT NULL | |
| osm_node_end | BIGINT | NOT NULL | |
| name | VARCHAR(255) | nullable | Street name |
| highway_type | VARCHAR(50) | NOT NULL | e.g., residential, primary |
| geometry | GEOMETRY(LINESTRING, 4326) | NOT NULL | PostGIS geometry column |
| length_meters | FLOAT | NOT NULL | |
| created_at | TIMESTAMP | NOT NULL, server_default=now() | |

**Indexes**: `ix_street_segment_city_neighborhood (city_id, neighborhood_id)`, GiST index on `geometry`  
**Relationships**: `city` (N:1), `neighborhood` (N:1)

### UserStreetCoverage

| Field | Type (PostgreSQL) | Constraints | Notes |
|-------|-------------------|-------------|-------|
| id | SERIAL | PK | |
| user_id | INTEGER | FK→users.id, NOT NULL | |
| street_segment_id | INTEGER | FK→street_segments.id, NOT NULL | |
| coverage_ratio | FLOAT | NOT NULL, default=0.0 | 0.0–1.0 |
| is_traveled | BOOLEAN | NOT NULL, default=false | True if ratio ≥ 0.80 |
| first_traveled_at | TIMESTAMP | nullable | |
| last_activity_id | INTEGER | FK→activities.id, nullable | |
| updated_at | TIMESTAMP | NOT NULL, server_default=now() | |

**Indexes**: UNIQUE (user_id, street_segment_id)  
**Relationships**: `user` (N:1), `street_segment` (N:1), `last_activity` (N:1)

### CoverageSnapshot

| Field | Type (PostgreSQL) | Constraints | Notes |
|-------|-------------------|-------------|-------|
| id | SERIAL | PK | |
| user_id | INTEGER | FK→users.id, NOT NULL | |
| city_id | INTEGER | FK→cities.id, NOT NULL | |
| neighborhood_id | INTEGER | FK→neighborhoods.id, nullable | |
| coverage_percentage | FLOAT | NOT NULL | 0.0–100.0 |
| total_streets_traveled | INTEGER | NOT NULL | |
| total_streets | INTEGER | NOT NULL | |
| is_milestone | BOOLEAN | NOT NULL, default=false | |
| milestone_label | VARCHAR(50) | nullable | Values: "25%", "50%", "75%", "100%" |
| snapshot_date | DATE | NOT NULL | |
| created_at | TIMESTAMP | NOT NULL, server_default=now() | |

**Indexes**: UNIQUE (user_id, city_id, neighborhood_id, snapshot_date)  
**Relationships**: `user` (N:1), `city` (N:1), `neighborhood` (N:1)

### RouteSuggestion

| Field | Type (PostgreSQL) | Constraints | Notes |
|-------|-------------------|-------------|-------|
| id | SERIAL | PK | |
| user_id | INTEGER | FK→users.id, NOT NULL | |
| city_id | INTEGER | FK→cities.id, NOT NULL | |
| neighborhood_id | INTEGER | FK→neighborhoods.id, nullable | |
| start_point | GEOMETRY(POINT, 4326) | NOT NULL | PostGIS geometry column |
| route_geometry | GEOMETRY(LINESTRING, 4326) | NOT NULL | PostGIS geometry column |
| distance_meters | FLOAT | NOT NULL | |
| estimated_duration_seconds | INTEGER | NOT NULL | |
| requested_distance_meters | FLOAT | NOT NULL | |
| untraveled_distance_meters | FLOAT | NOT NULL | |
| untraveled_ratio | FLOAT | NOT NULL | 0.0–1.0 |
| created_at | TIMESTAMP | NOT NULL, server_default=now() | |

**Indexes**: GiST index on `start_point`, GiST index on `route_geometry`  
**Relationships**: `user` (N:1), `city` (N:1), `neighborhood` (N:1), `segments` (1:N)

### RouteSuggestionSegment

| Field | Type (PostgreSQL) | Constraints | Notes |
|-------|-------------------|-------------|-------|
| id | SERIAL | PK | |
| route_suggestion_id | INTEGER | FK→route_suggestions.id, ON DELETE CASCADE, NOT NULL | |
| street_segment_id | INTEGER | FK→street_segments.id, NOT NULL | |
| sequence_order | INTEGER | NOT NULL | |
| is_untraveled | BOOLEAN | NOT NULL | |

**Relationships**: `route_suggestion` (N:1), `street_segment` (N:1)

## Spatial Index Strategy

All geometry columns receive GiST indexes (created automatically by GeoAlchemy2 when using PostGIS). No explicit R-tree virtual table queries are needed — PostGIS's query planner uses GiST indexes transparently via the `&&` (bounding box overlap) operator when `ST_*` functions are applied.

## Validation Rules

- `coverage_ratio`: 0.0 ≤ value ≤ 1.0
- `is_traveled`: derived from `coverage_ratio >= 0.80`
- `coverage_percentage`: 0.0 ≤ value ≤ 100.0
- `sync_status`: enum of valid values (idle, importing, syncing, complete, error, revoked)
- `import_status`: enum of valid values (pending, polyline_imported, streams_imported, matched, error, gps_quality_warning)
- All geometry columns: SRID must be 4326 (WGS84)

## State Transitions

### sync_status (User)
```
idle → importing → syncing → complete
  ↑                  │
  └──── error ←──────┘
         ↓
       revoked
```

### import_status (Activity)
```
pending → polyline_imported → streams_imported → matched
                                    │
                                    └── gps_quality_warning
           error ←──── (any state)
```

## Type Changes from SQLite

| Column | SQLite Type | PostgreSQL Type | Migration Notes |
|--------|------------|-----------------|-----------------|
| All geometry columns | GEOMETRY (SpatiaLite) | GEOMETRY (PostGIS) | Same GeoAlchemy2 type; different backend |
| Integer PKs | INTEGER autoincrement | SERIAL | SQLAlchemy handles this transparently |
| DateTime columns | TEXT (ISO 8601) | TIMESTAMP | Native timestamp type; no parsing needed |
| Boolean columns | INTEGER (0/1) | BOOLEAN | Native boolean type |
| Date columns | TEXT (ISO 8601) | DATE | Native date type |

All type conversions are handled transparently by SQLAlchemy's dialect system — no application code changes are needed for type mapping.
