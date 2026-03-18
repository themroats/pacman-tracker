# Research: Application Stability & Hardening

**Feature**: 002-app-stability-hardening | **Date**: 2026-03-14

## R1: Auth Token O(1) Lookup Strategy

**Unknown**: How to replace the O(n) decrypt-all-compare pattern in `deps.py` with O(1) lookup.

**Current**: `get_current_user()` loads ALL users, decrypts each `access_token_encrypted` (Fernet), and compares to the Bearer token. O(n) with expensive crypto per user.

**Decision**: Add an indexed `access_token_hash` column (SHA-256 of the plaintext token) to the `User` model. On login/token-refresh, compute and store the hash alongside the encrypted token. On auth, hash the incoming Bearer token and do a single indexed query: `WHERE access_token_hash = ?`.

**Rationale**: 
- SHA-256 is a one-way hash — safe to store unencrypted (cannot reverse to get the Strava token)
- Lookup becomes a single indexed query: O(1) 
- The encrypted token column remains for cases where the plaintext needs to be recovered (e.g., calling Strava API)
- No new dependencies — `hashlib` is in the Python stdlib
- Minimal schema change — one new TEXT column with a unique index

**Alternatives considered**:
- JWT sessions: Would require a full session management rewrite; overkill for this hardening pass
- Redis token cache: Adds infrastructure dependency; unnecessary at current scale
- Encrypted lookup via deterministic encryption: Fernet is non-deterministic (includes timestamp), so same plaintext produces different ciphertext — cannot be used for lookup

## R2: Sync State Machine Implementation

**Unknown**: How to implement the `idle → syncing → complete → idle` state machine reliably.

**Current**: `sync_runtime.py` uses process-local `set[int]` for tracking active jobs. `user.sync_status` in DB is the persistent state, but transitions are not enforced — any string can be written. Stale recovery only works if the same process restarts.

**Decision**: Implement transitions as a validated state machine in the `User` model:
1. Define valid transitions as a dict: `{current_state: [allowed_next_states]}`
2. Add a `transition_sync_status(new_status)` method that validates the transition
3. Add `sync_started_at` timestamp column for stale-job detection (if `syncing` for more than 5 minutes and no in-process job, mark as error)
4. On app startup (lifespan), query all users with `sync_status IN ('syncing', 'importing')` and reset to `error`
5. "complete" is a transient state — set to "complete" on successful sync, frontend observes it, then backend resets to "idle" on next status poll

**Rationale**:
- Database-backed state is the only reliable source of truth for single-process SQLite deployment
- `sync_started_at` provides a timeout mechanism without needing distributed locks
- Startup recovery query is simple and handles all crash scenarios
- State machine validation prevents invalid transitions from code bugs

**Alternatives considered**:
- Redis-backed job queue: Adds infrastructure; unnecessary for single-process deployment
- Celery task queue: Same — too heavy for current scale
- Keep process-local set: Broken on restart, which is the problem we're fixing

## R3: Frontend Toast Notification Pattern

**Unknown**: How to implement toast notifications across all pages without a new dependency.

**Current**: `ErrorBoundary.tsx` exists but only catches render errors. `useAppStore` has `error: string | null` but it's rarely consumed. All pages use `.catch(() => {})`.

**Decision**: Build a minimal toast system using Zustand:
1. Add a `toasts: Toast[]` array to the Zustand store with `addToast(message, type)` and `removeToast(id)` actions
2. Create a `<ToastContainer>` component that renders toasts from the store, positioned fixed bottom-right
3. Toasts auto-dismiss after 5 seconds with a CSS transition
4. Modify `api/client.ts` to expose a global `onError` hook that `addToast` plugs into
5. Replace all `.catch(() => {})` patterns with `.catch((e) => addToast(e.message, 'error'))`

**Rationale**:
- Zero new dependencies — uses existing Zustand store + CSS
- Centralized via API client error hook — no need to modify every individual call
- Type-safe: Toast type = `'error' | 'warning' | 'success' | 'info'`
- Auto-dismiss prevents toast buildup; manual dismiss also available

**Alternatives considered**:
- react-hot-toast library: Good library but adds a dependency; constitution prohibits speculative dependencies
- Browser Notification API: Requires user permission; invasive for API errors
- Inline error banners per-component: Too scattered; requires touching every component individually

## R4: N+1 Coverage Query Fix

**Unknown**: Best approach to batch the neighborhood coverage query.

**Current**: `city_coverage()` in `coverage.py` calls `_neighborhood_coverage(db, user.id, n)` in a loop for each neighborhood. Each call runs a LEFT JOIN + aggregate query. City with 50 neighborhoods = 51 queries.

**Decision**: Replace the loop with a single GROUP BY query:
```sql
SELECT 
  ss.neighborhood_id,
  COUNT(ss.id) AS total,
  COUNT(usc.id) AS traveled,
  COALESCE(SUM(CASE WHEN usc.is_traveled THEN ss.length_meters ELSE 0 END), 0) AS traveled_length
FROM street_segments ss
LEFT JOIN user_street_coverage usc 
  ON usc.street_segment_id = ss.id 
  AND usc.user_id = :user_id 
  AND usc.is_traveled = true
WHERE ss.neighborhood_id IN (:neighborhood_ids)
GROUP BY ss.neighborhood_id
```

Then join with neighborhood metadata in Python.

**Rationale**:
- Single query regardless of neighborhood count
- Uses the same JOIN pattern as the current per-neighborhood query, just grouped
- No schema changes needed
- SpatiaLite/SQLite supports GROUP BY with aggregates

**Alternatives considered**:
- Materialized view: SQLite doesn't support materialized views natively
- Precomputed coverage table: Adds complexity for cache invalidation on every activity import
- Application-level caching: Stale data risk; invalidation is complex

## R5: Webhook Error Handling Strategy

**Unknown**: Should webhook handler return non-200 to allow Strava retry?

**Current**: `strava_webhook_event()` always returns `{"status": "received"}` (200). Inner `handle_webhook_event()` catches all exceptions with `pass`.

**Decision**: 
1. Log all caught exceptions at ERROR level in `handle_webhook_event()` (replace `pass` with `logger.exception(...)`)
2. Let exceptions propagate from `handle_webhook_event()` to the route handler
3. In the route handler, catch specific recoverable errors (e.g., `TokenRevokedError`) and handle them (mark user as revoked, return 200)
4. Let transient errors (network, DB) propagate as 500 → Strava will retry
5. Unknown user webhooks still return 200 (can't retry for non-existent user)

**Rationale**:
- Strava retries on non-200 responses (documented behavior)
- Token revocation is not retryable → return 200 after marking user
- DB/network errors are transient → return 500 to trigger retry
- Logging provides visibility into all error types

**Alternatives considered**:
- Always return 200 + internal retry queue: Adds complexity; Strava's built-in retry is sufficient
- Dead-letter queue for failed events: Overkill at current scale

## R6: Activity Deduplication Under Concurrent Imports

**Unknown**: How to handle the race condition when webhook + manual sync import the same activity simultaneously.

**Current**: Dedup check is `SELECT ... WHERE strava_activity_id = ?` before INSERT. Two concurrent processes can both find no existing record and both INSERT, causing a UNIQUE constraint violation.

**Decision**: 
1. Add `UNIQUE` constraint on `(strava_activity_id)` column if not already present
2. Catch `IntegrityError` on INSERT and treat it as "already exists" (skip gracefully)
3. This is a standard "INSERT OR IGNORE" pattern

**Rationale**:
- Database-level constraint is the only race-safe dedup mechanism
- `IntegrityError` catch is a well-established pattern for concurrent inserts
- No locking needed — the constraint handles it
- SQLite serializes writes anyway, but the pattern is correct for future migration to PostgreSQL

**Alternatives considered**:
- SELECT FOR UPDATE locking: SQLite doesn't support row-level locking
- Application-level mutex: Process-local; doesn't help with multi-process
- INSERT OR IGNORE SQL: SQLAlchemy supports this but it's dialect-specific; catching IntegrityError is more portable

## R7: OSRM Health Check Pattern

**Unknown**: How to detect OSRM unavailability and degrade gracefully.

**Current**: `config.py` has `osrm_url: str = "http://localhost:5000"`. Route suggestion endpoints call OSRM directly. If OSRM is down, the request hangs or returns a cryptic error.

**Decision**:
1. Add a `/health` check to the routes endpoint that pings OSRM at startup and caches the result
2. Add an `osrm_available` flag to the backend health/status response
3. Route suggestion endpoint returns a clean error with `"OSRM_UNAVAILABLE"` code when flag is false
4. Frontend checks this flag and disables the route form with a message when OSRM is unavailable
5. Re-check OSRM availability periodically (every 60 seconds) or on first route request

**Rationale**:
- Fail-fast rather than letting users wait for a timeout
- Backend controls the degradation logic — frontend just reads the flag
- Periodic re-check allows recovery if OSRM comes online later

**Alternatives considered**:
- Frontend-side health check: Violates constitution principle I (frontend must not call external APIs)
- Always attempt + fast timeout: User still sees an error; degradation should be proactive
