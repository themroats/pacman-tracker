# API Contract Changes: Application Stability & Hardening

**Feature**: 002-app-stability-hardening | **Date**: 2026-03-14

This document describes changes to the existing REST API contracts. Only modified or new behaviors are listed — unchanged endpoints are omitted.

## Authentication Changes

### All Data Endpoints — Add Auth Requirement

The following endpoints currently lack `user: User = Depends(get_current_user)` and must add it:

| Endpoint | Current Auth | Required Auth |
|----------|-------------|---------------|
| `GET /api/v1/activities` | None | Bearer token (user-scoped) |
| `GET /api/v1/activities/geojson` | None | Bearer token (user-scoped) |
| `GET /api/v1/progress/city/{city_id}` | None (hardcoded user_id=1) | Bearer token (user-scoped) |
| `GET /api/v1/progress/stats` | None (hardcoded user_id=1) | Bearer token (user-scoped) |

**Unauthenticated response** (all endpoints):
```json
// 401 Unauthorized
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Missing or invalid authorization header",
    "details": {}
  }
}
```

### Auth Lookup — O(1) Behavior Change

`get_current_user()` changes from decrypting all tokens to a single indexed lookup by `access_token_hash`. No contract change visible to clients — same Bearer token in, same User out.

## Error Response Changes

### Standardized Error Codes

All error responses follow the existing `AppError` format. New error codes introduced:

| Code | HTTP Status | When |
|------|-------------|------|
| `OSRM_UNAVAILABLE` | 503 | Route suggestion requested but OSRM service is unreachable |
| `SYNC_IN_PROGRESS` | 409 | User triggers sync while another is already running |
| `TOKEN_REVOKED` | 401 | Strava token has been revoked; user must re-authenticate |
| `VALIDATION_ERROR` | 400 | Input validation failure (coordinates, distance, bbox, IDs) |

### Webhook Endpoint — Non-200 on Failure

`POST /api/v1/webhook/strava`

**Current**: Always returns `200 {"status": "received"}`
**New behavior**:
- Returns `200` on success or for non-retryable situations (unknown user, token revoked)
- Returns `500` on transient failures (DB error, network error) to trigger Strava retry

## Validation Changes

### Route Suggestion Request

`POST /api/v1/routes/suggest`

**Request body changes:**

| Field | Current Validation | New Validation |
|-------|-------------------|----------------|
| `distance_meters` | `gt=0` | `gt=0, le=50000` (50 km max) |
| `start_point.lng` | No validation | `ge=-180, le=180` |
| `start_point.lat` | No validation | `ge=-90, le=90` |
| `city_id` | No validation | `gt=0` |
| `neighborhood_id` | No validation | `gt=0` (when provided) |

**New error response for OSRM unavailable:**
```json
// 503 Service Unavailable
{
  "error": {
    "code": "OSRM_UNAVAILABLE",
    "message": "Route suggestions are temporarily unavailable",
    "details": {}
  }
}
```

### Coverage Endpoint — BBox Validation

`GET /api/v1/coverage/city/{city_id}/streets`

**Query parameter `bbox` changes:**

| Current | New |
|---------|-----|
| Invalid bbox silently returns empty | Returns 400 with descriptive error |
| No range validation | `lat: -90..90, lng: -180..180` |

### Entity ID Validation

All path parameters accepting entity IDs (`city_id`, `neighborhood_id`) will return `400 VALIDATION_ERROR` for non-positive integers.

## Sync Status Response Changes

`GET /api/v1/sync/status`

**Response schema unchanged**, but `status` field now follows a strict state machine:

| Status Value | Meaning | Frontend Action |
|-------------|---------|-----------------|
| `idle` | No sync running | Normal UI |
| `syncing` | Sync in progress | Show progress, poll every 5s |
| `complete` | Sync just finished successfully | Show success toast, stop polling |
| `error` | Sync failed | Show error toast, enable retry |
| `revoked` | Strava token revoked | Show reconnect banner |

**New field in response:**
```json
{
  "status": "error",
  "error_message": "Previous sync was interrupted by an app restart. Please run it again.",
  ...
}
```

`error_message` is already in the response schema but was only populated for stale recovery. It will now also be populated for all error states.

## Health Endpoint

`GET /health`

**New response fields:**
```json
{
  "status": "ok",
  "osrm_available": true
}
```

`osrm_available` tells the frontend whether route suggestions will work.
