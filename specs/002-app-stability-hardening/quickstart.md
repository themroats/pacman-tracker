# Quickstart: Application Stability & Hardening

**Feature**: 002-app-stability-hardening | **Date**: 2026-03-14

## What This Feature Does

Fixes ~60 issues across the existing Pac-Man Tracker application to make it work reliably:

- **Stops silent failures**: Every API error, import failure, and exception now either shows a toast notification to the user or gets logged at ERROR level. No more `.catch(() => {})`.
- **Locks down user data**: All data endpoints require authentication and return only the current user's data. No more cross-user data leaks.
- **Makes sync resilient**: Strava sync follows a strict state machine that handles token revocation, server restarts, and transient failures. Users are never stuck in a "syncing" state.
- **Adds input validation**: Coordinates, distances, bounding boxes, and entity IDs are all validated with friendly error messages.
- **Speeds up key queries**: Coverage queries batched into single GROUP BY instead of N+1 per neighborhood. Auth lookup O(1) via token hash index.

## Key Architecture Decisions

1. **Toast notifications** (not inline banners) for API errors — zero new dependencies, built on Zustand store
2. **SHA-256 token hash** for O(1) auth lookup — stored alongside encrypted token, indexed
3. **Database-backed sync state machine** with `sync_started_at` for timeout detection — no Redis needed
4. **Graceful OSRM degradation** — health check flag disables route form when service unavailable
5. **IntegrityError catch** for concurrent activity dedup — database constraint is the safety net

## Prerequisites

- Backend: Python 3.12+, SpatiaLite extension
- Frontend: Node.js, npm
- Existing database with users/activities (one-time migration needed for `access_token_hash` backfill)

## How to Verify

### Error Feedback (US1)
1. Start app, authenticate
2. Stop the backend server
3. Navigate to any page → toast notification appears saying API is unreachable
4. Restart backend → data loads normally

### User Data Isolation (US2)
1. Create two test users (two Strava accounts)
2. Import activities for both
3. Auth as User A → see only User A's activities
4. Auth as User B → see only User B's activities
5. Call any data endpoint without auth → 401

### Sync Resilience (US3)
1. Trigger a sync
2. While syncing, revoke Strava token → status updates to "revoked", reconnect banner appears
3. Trigger another sync while one is in progress → rejected with "sync already in progress"
4. Restart server while sync is "syncing" → on restart, status resets to "error"

### Coverage Accuracy (US4)
1. Import same activity set twice → second import skips duplicates, no errors
2. View neighborhood coverage → data loads in ≤2 DB queries (verify via query log)

### Frontend UX (US5)
1. Navigate each page on throttled network → loading spinners visible
2. Trigger API errors → toast notifications appear with message

### Input Validation (US6)
1. Enter lat=999 in route form → inline validation error
2. Request route with distance=999km → rejected with max-distance error
3. Submit invalid bbox → 400 error with description

## Files Modified

### Backend (existing files only)
- `app/api/deps.py` — O(1) auth lookup
- `app/api/activities.py` — add auth dependency
- `app/api/progress.py` — replace hardcoded user ID with auth
- `app/api/coverage.py` — batch N+1 query
- `app/api/routes.py` — input validation, OSRM health check
- `app/api/sync.py` — sync state machine
- `app/api/webhook.py` — non-200 on failure
- `app/models/user.py` — `access_token_hash`, `sync_started_at`, state machine method
- `app/models/activity.py` — expand valid import statuses
- `app/schemas/route.py` — validation bounds
- `app/services/importer.py` — error logging, IntegrityError catch
- `app/services/webhook.py` — error logging, exception propagation
- `app/services/sync_runtime.py` — stale sync timeout detection
- `app/database.py` — FK pragma
- `app/main.py` — startup recovery, health check enhancement

### Frontend (existing files only)
- `src/api/client.ts` — error hook for toast integration
- `src/store/index.ts` — toast state, OSRM flag
- `src/pages/*.tsx` — replace `.catch(() => {})` with toast calls, add loading states
- `src/components/SyncStatus.tsx` — handle "complete" state
- New: `src/components/common/ToastContainer.tsx` — toast notification renderer
- `src/App.tsx` — mount ToastContainer
