# API Contracts: Strava Street Mapper

**Feature**: 001-strava-street-mapper  
**Date**: 2026-02-28  
**Base URL**: `http://localhost:8000/api/v1`  
**Format**: JSON (all requests/responses)  
**Auth**: Bearer token (Strava OAuth access token forwarded as session)

---

## Authentication

### `GET /auth/strava`

Redirect user to Strava OAuth authorization page.

**Response**: `302 Redirect` to `https://www.strava.com/oauth/authorize?...`

---

### `GET /auth/strava/callback`

Handle Strava OAuth callback after user authorization.

**Query Parameters**:
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| code | string | yes | Authorization code from Strava |
| scope | string | yes | Granted scopes |
| state | string | yes | CSRF token for validation |

**Response** `200 OK`:
```json
{
  "user_id": 1,
  "display_name": "Jane Runner",
  "access_token": "session-token-here",
  "home_city": null,
  "sync_status": "importing"
}
```

**Error** `400 Bad Request`: Invalid code or state mismatch.

---

### `POST /auth/logout`

End user session.

**Response** `200 OK`:
```json
{ "message": "Logged out" }
```

---

## Activities

### `GET /activities`

List user's imported activities with optional filters.

**Query Parameters**:
| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| sport_type | string | no | all | Filter: "Run", "Walk", "Ride" |
| start_date | ISO date | no | — | Filter: activities on or after |
| end_date | ISO date | no | — | Filter: activities on or before |
| min_distance | float | no | — | Filter: minimum distance in meters |
| max_distance | float | no | — | Filter: maximum distance in meters |
| city_id | integer | no | — | Filter: activities in this city |
| page | integer | no | 1 | Pagination page |
| per_page | integer | no | 50 | Items per page (max 200) |

**Response** `200 OK`:
```json
{
  "activities": [
    {
      "id": 42,
      "strava_activity_id": 1234567890,
      "name": "Morning Run in Capitol Hill",
      "sport_type": "Run",
      "start_date": "2026-02-15T07:30:00Z",
      "distance_meters": 8542.3,
      "duration_seconds": 2760,
      "moving_time_seconds": 2650,
      "pace_min_per_km": 5.17,
      "has_gps": true,
      "is_on_street": true,
      "city_name": "Seattle"
    }
  ],
  "total": 234,
  "page": 1,
  "per_page": 50
}
```

---

### `GET /activities/{id}`

Get detailed activity with GPS trace for map rendering.

**Response** `200 OK`:
```json
{
  "id": 42,
  "strava_activity_id": 1234567890,
  "name": "Morning Run in Capitol Hill",
  "sport_type": "Run",
  "start_date": "2026-02-15T07:30:00Z",
  "distance_meters": 8542.3,
  "duration_seconds": 2760,
  "moving_time_seconds": 2650,
  "pace_min_per_km": 5.17,
  "has_gps": true,
  "is_on_street": true,
  "gps_trace": {
    "type": "LineString",
    "coordinates": [[-122.3201, 47.6205], [-122.3198, 47.6210], ...]
  }
}
```

**Error** `404 Not Found`: Activity does not exist or belongs to another user.

---

### `GET /activities/{id}/geojson`

Get activity as GeoJSON Feature for direct map rendering.

**Response** `200 OK`:
```json
{
  "type": "Feature",
  "properties": {
    "id": 42,
    "name": "Morning Run in Capitol Hill",
    "sport_type": "Run",
    "distance_meters": 8542.3,
    "start_date": "2026-02-15T07:30:00Z"
  },
  "geometry": {
    "type": "LineString",
    "coordinates": [[-122.3201, 47.6205], [-122.3198, 47.6210], ...]
  }
}
```

---

### `GET /activities/geojson`

Get all user activities as a GeoJSON FeatureCollection (for bulk map rendering).

**Query Parameters**: Same filters as `GET /activities`.

**Response** `200 OK`:
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": { "id": 42, "name": "...", "sport_type": "Run", ... },
      "geometry": { "type": "LineString", "coordinates": [...] }
    }
  ]
}
```

---

## Sync

### `GET /sync/status`

Get current sync status for the authenticated user.

**Response** `200 OK`:
```json
{
  "status": "syncing",
  "total_activities": 234,
  "imported_activities": 180,
  "matched_activities": 150,
  "last_sync_at": "2026-02-28T10:30:00Z",
  "error_message": null
}
```

---

### `POST /sync/trigger`

Manually trigger an incremental sync of new Strava activities.

**Response** `202 Accepted`:
```json
{
  "message": "Sync started",
  "status": "syncing"
}
```

---

## Webhooks

### `GET /webhook/strava`

Strava webhook subscription verification (called by Strava during subscription setup).

**Query Parameters**:
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| hub.mode | string | yes | Always "subscribe" |
| hub.challenge | string | yes | Challenge string to echo back |
| hub.verify_token | string | yes | Token to validate against app config |

**Response** `200 OK`:
```json
{
  "hub.challenge": "challenge-string-from-strava"
}
```

---

### `POST /webhook/strava`

Receive Strava push event notifications for new/updated/deleted activities.

**Request Body** (from Strava):
```json
{
  "aspect_type": "create",
  "event_time": 1709164800,
  "object_id": 1234567890,
  "object_type": "activity",
  "owner_id": 98765,
  "subscription_id": 12345,
  "updates": {}
}
```

| Field | Type | Description |
|-------|------|-------------|
| aspect_type | string | "create", "update", or "delete" |
| object_id | integer | Strava activity ID |
| object_type | string | Always "activity" for our use case |
| owner_id | integer | Strava athlete ID |

**Response** `200 OK`:
```json
{ "status": "received" }
```

**Behavior**: On `create`/`update`, triggers an incremental sync for the matching user. On `delete`, marks the local activity as deleted.

---

## Coverage

### `GET /coverage/city/{city_id}`

Get city-wide coverage summary with per-neighborhood breakdown.

**Response** `200 OK`:
```json
{
  "city": {
    "id": 1,
    "name": "Seattle",
    "coverage_percentage": 12.5,
    "streets_traveled": 1250,
    "streets_total": 10000,
    "distance_traveled_m": 45000.0,
    "distance_total_m": 360000.0
  },
  "neighborhoods": [
    {
      "id": 10,
      "name": "Capitol Hill",
      "coverage_percentage": 45.2,
      "streets_traveled": 90,
      "streets_total": 199,
      "distance_traveled_m": 12300.0,
      "distance_total_m": 27200.0
    }
  ]
}
```

---

### `GET /coverage/neighborhood/{neighborhood_id}`

Get detailed coverage for a neighborhood.

**Response** `200 OK`:
```json
{
  "neighborhood": {
    "id": 10,
    "name": "Capitol Hill",
    "city_name": "Seattle",
    "coverage_percentage": 45.2,
    "streets_traveled": 90,
    "streets_total": 199
  },
  "boundary": {
    "type": "Polygon",
    "coordinates": [...]
  }
}
```

---

### `GET /coverage/neighborhood/{neighborhood_id}/streets`

Get street segments for a neighborhood with coverage status (for map rendering).

> **Note**: This endpoint is a convenience alias. The same data is available via `GET /coverage/city/{city_id}/streets?neighborhood_id={id}`. Both are retained for URL clarity.

**Response** `200 OK`:
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "id": 500,
        "name": "E Pine St",
        "highway_type": "residential",
        "length_meters": 245.3,
        "is_traveled": true,
        "coverage_ratio": 0.92,
        "first_traveled_at": "2026-01-15"
      },
      "geometry": {
        "type": "LineString",
        "coordinates": [[-122.3201, 47.6205], [-122.3150, 47.6205]]
      }
    }
  ]
}
```

---

### `GET /coverage/city/{city_id}/streets`

Get all street segments for a city with coverage status (GeoJSON).

**Query Parameters**:
| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| neighborhood_id | integer | no | — | Filter to specific neighborhood |
| status | string | no | all | "traveled", "untraveled", or "all" |
| bbox | string | no | — | Bounding box filter: "minLng,minLat,maxLng,maxLat" |

**Response** `200 OK`: Same GeoJSON FeatureCollection format as neighborhood streets.

---

## Routes

### `POST /routes/suggest`

Generate a route suggestion prioritizing untraveled streets.

**Request Body**:
```json
{
  "start_point": { "lng": -122.3201, "lat": 47.6205 },
  "distance_meters": 5000,
  "city_id": 1,
  "neighborhood_id": 10
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| start_point | object | yes | Starting location {lng, lat} |
| distance_meters | float | yes | Desired route distance (meters) |
| city_id | integer | yes | City context |
| neighborhood_id | integer | no | Target neighborhood (optional) |

**Response** `200 OK`:
```json
{
  "route": {
    "id": 7,
    "distance_meters": 5120.5,
    "estimated_duration_seconds": 2560,
    "untraveled_distance_meters": 3450.2,
    "untraveled_ratio": 0.67,
    "geometry": {
      "type": "LineString",
      "coordinates": [[-122.3201, 47.6205], ...]
    }
  },
  "segments": [
    {
      "street_name": "E Pine St",
      "is_untraveled": true,
      "length_meters": 245.3
    }
  ]
}
```

**Error** `400 Bad Request`: Invalid start point or distance.  
**Response** `200 OK` (all covered):
```json
{
  "route": null,
  "message": "All streets in Capitol Hill are covered! Try a neighboring area.",
  "suggested_neighborhoods": [
    { "id": 11, "name": "First Hill", "coverage_percentage": 22.0 }
  ]
}
```

---

### `GET /routes/history`

Get user's past route suggestions.

**Response** `200 OK`:
```json
{
  "routes": [
    {
      "id": 7,
      "created_at": "2026-02-28T14:00:00Z",
      "distance_meters": 5120.5,
      "untraveled_ratio": 0.67,
      "neighborhood_name": "Capitol Hill",
      "city_name": "Seattle"
    }
  ]
}
```

---

## Progress

### `GET /progress/city/{city_id}`

Get progress timeline and milestones for a city.

**Response** `200 OK`:
```json
{
  "city_name": "Seattle",
  "current_coverage_percentage": 12.5,
  "milestones": [
    {
      "label": "25%",
      "neighborhood_name": "Capitol Hill",
      "reached": true,
      "date": "2026-02-01"
    },
    {
      "label": "50%",
      "neighborhood_name": "Capitol Hill",
      "reached": false,
      "date": null
    }
  ],
  "timeline": [
    {
      "date": "2026-01-01",
      "coverage_percentage": 2.1,
      "streets_traveled": 210
    },
    {
      "date": "2026-02-01",
      "coverage_percentage": 8.3,
      "streets_traveled": 830
    }
  ]
}
```

---

### `GET /progress/stats`

Get overall user statistics.

**Response** `200 OK`:
```json
{
  "total_activities": 234,
  "total_distance_meters": 1850000,
  "total_unique_streets": 1250,
  "cities": [
    {
      "city_name": "Seattle",
      "coverage_percentage": 12.5,
      "streets_traveled": 1250,
      "streets_total": 10000
    }
  ]
}
```

---

## Cities

### `GET /cities`

List all supported cities.

**Response** `200 OK`:
```json
{
  "cities": [
    {
      "id": 1,
      "name": "Seattle",
      "state": "Washington",
      "total_street_segments": 10000,
      "total_neighborhoods": 53
    }
  ]
}
```

---

### `GET /cities/{city_id}/neighborhoods`

List neighborhoods for a city.

**Response** `200 OK`:
```json
{
  "neighborhoods": [
    {
      "id": 10,
      "name": "Capitol Hill",
      "total_street_segments": 199,
      "coverage_percentage": 45.2
    }
  ]
}
```

---

### `GET /cities/{city_id}/neighborhoods/{neighborhood_id}/boundary`

Get neighborhood boundary as GeoJSON for map rendering.

**Response** `200 OK`:
```json
{
  "type": "Feature",
  "properties": {
    "id": 10,
    "name": "Capitol Hill",
    "coverage_percentage": 45.2
  },
  "geometry": {
    "type": "Polygon",
    "coordinates": [...]
  }
}
```

---

## Error Format

All errors follow a consistent format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable description",
    "details": {}
  }
}
```

**Standard error codes**:
| HTTP Status | Code | Description |
|-------------|------|-------------|
| 400 | VALIDATION_ERROR | Invalid request parameters |
| 401 | UNAUTHORIZED | Missing or invalid auth token |
| 403 | FORBIDDEN | Access denied to resource |
| 404 | NOT_FOUND | Resource does not exist |
| 429 | RATE_LIMITED | Too many requests |
| 500 | INTERNAL_ERROR | Server error |
| 503 | STRAVA_UNAVAILABLE | Strava API is unreachable |
