# Phase 1 Data Model: Local Browser-Based Verification Harness

**Feature**: `008-browser-verification-harness` | **Date**: 2026-06-15

This feature introduces **no new database schema**. It seeds the *existing* ORM models into an isolated verification database and adds non-persistent harness entities (runs, forced responses, results) that live only in the test process. Below, entities are grouped by where they live.

---

## A. Seeded database entities (existing models, populated by the seed scripts)

The verification database (`pacman_verify`) is populated from the frozen Seattle snapshot (streets/neighborhoods/city) plus a layered demo user and sample data. Field references below come from the existing models.

### Demo User → `users` table (`User`)
The single user the bypass resolves to. Must be the **only** row in `users` so the bypass ("first user") is deterministic.

| Field | Value for demo user | Notes |
|-------|--------------------|-------|
| `id` | 1 (first/only) | Bypass returns the first user |
| `strava_athlete_id` | Synthetic non-real ID (e.g., `9000000001`) | Not a real athlete |
| `display_name` | e.g., "Demo Runner" | Also written to frontend `localStorage.display_name` |
| `access_token_encrypted` / `refresh_token_encrypted` | Encrypted placeholder values | Never used (bypass skips token validation); MUST NOT be real tokens |
| `token_expires_at` | Far-future timestamp | Avoids refresh attempts |
| `strava_scope` | `"read,activity:read"` | Minimal scope string |
| `home_city_id` | Seattle city id from snapshot | Links demo user to seeded city |
| `sync_status` | `"complete"` | Stable baseline; no in-flight sync |

**Validation/constraints**: exactly one row; `sync_status` ∈ `VALID_SYNC_STATUSES`; no real private tokens (Principle III, FR-004d).

### Street Snapshot → `cities`, `neighborhoods`, `street_segments` (restored, not seeded by script)
Real Seattle geometry restored from the frozen `pg_dump`. Treated as **read-only baseline**; the data-only reset does NOT truncate these tables (only re-restored during a clean full bring-up).

| Table | Role | Reset behavior |
|-------|------|----------------|
| `cities` (`City`) | Seattle city + projected CRS metadata | Preserved on data-only reset |
| `neighborhoods` (`Neighborhood`) | Neighborhood boundaries | Preserved on data-only reset |
| `street_segments` (`StreetSegment`) | ~300k walkable segments w/ PostGIS geometry | Preserved on data-only reset |

### Sample Activities → `activities` table (`Activity`)
A handful of synthetic activities giving the map/coverage pages content.

| Field | Value | Notes |
|-------|-------|-------|
| `user_id` | demo user id | |
| `strava_activity_id` | Synthetic IDs | Unique, non-real |
| `sport_type` | e.g., `"Run"` | |
| `gps_trace` / `has_gps` | LINESTRING over real Seattle streets / `true` | Enough to drive coverage |
| `import_status` | `"matched"` | Stable terminal state |

### Sample Coverage → `user_street_coverages` + `coverage_snapshots`
Derived coverage so dashboards render non-empty.

| Table | Role | Reset behavior |
|-------|------|----------------|
| `user_street_coverages` (`UserStreetCoverage`) | Per-street coverage ratio/traveled flags for demo user | Truncated + reseeded on data-only reset |
| `coverage_snapshots` (`CoverageSnapshot`) | Progress/milestone points for demo user | Truncated + reseeded on data-only reset |

**Validation**: `coverage_ratio` ∈ [0,1]; `is_traveled` set per `TRAVELED_THRESHOLD` (0.80); unique `(user_id, street_segment_id)`.

### Run-accumulated data (cleared on reset)
Tables that verification activity may mutate and that the data-only reset MUST truncate back to baseline — e.g., generated route suggestions (`routes`/`plans` per `route.py`/`plan.py`). Enumerated precisely during implementation; the reset script truncates these and reseeds the fixed sample set.

---

## B. Non-persistent harness entities (test-process only)

These exist only within a Playwright run; they are NOT stored in any database.

### Verification Run
A single attempt to confirm a fix works.

| Field | Description |
|-------|-------------|
| `target_pages` | Protected page(s) exercised (e.g., coverage dashboard, map) |
| `actions` | Ordered interactions (navigate, click, input, toggle) |
| `forced_responses` | Optional list of Forced Response Scenarios applied |
| `evidence` | Captured page content, console errors, network outcomes |
| `outcome` | `pass` | `fail` |

### Forced Response Scenario
A configured browser-layer response injected via Playwright `page.route()`.

| Field | Description | Validation |
|-------|-------------|-----------|
| `url_pattern` | Endpoint/route glob to intercept | Must match a real frontend call |
| `status` | Synthetic HTTP status (e.g., 401, 503, 404) | Valid HTTP status |
| `body` | Synthetic response body | JSON consistent with the endpoint's schema |
| `applies_to` | Which page action triggers it | |

Backend is unchanged; interception is browser-side only (FR-008).

### Verification Result
Outcome record for a run.

| Field | Description |
|-------|-------------|
| `outcome` | `pass` | `fail` |
| `expected_vs_unexpected` | Distinguishes "expected error UI appeared" from "unexpected error" (FR-007, US3) |
| `evidence` | Page content snapshot, visible/console errors, network request→response outcomes |
| `notes` | Optional human/agent-readable summary |

---

## C. Warm-state (process-local) reset targets (FR-018)

Not data tables, but in-process state the data-only reset MUST clear between warm runs (confirmed in code):

| State | Location | Reset action |
|-------|----------|--------------|
| OSRM availability cache | `app.services.routing._osrm_available` (module global) | Set to `None` / `check_osrm_available(force=True)` |
| Active sync-job tracking | sync service `clear_active_sync_jobs()` | Call to clear |

---

## Entity relationships (seeded data)

```text
City (Seattle, from snapshot)
 ├── Neighborhood* (from snapshot)
 └── StreetSegment* (from snapshot)
        ▲
        │ references
Demo User (id=1, only user)
 ├── Activity* (sample, gps_trace over real streets)
 ├── UserStreetCoverage* (per-street, references StreetSegment)
 └── CoverageSnapshot* (progress points)
```

`*` = many. Snapshot tables are read-only baseline; user/activity/coverage rows are seeded/reset.
