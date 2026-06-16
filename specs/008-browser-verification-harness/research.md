# Phase 0 Research: Local Browser-Based Verification Harness

**Feature**: `008-browser-verification-harness` | **Date**: 2026-06-15

All `NEEDS CLARIFICATION` items were resolved during the `/speckit.clarify` session (5 questions). This document consolidates the resulting decisions plus best-practice research for the chosen technologies. No open unknowns remain.

---

## Decision 1: Browser automation tool — Playwright

- **Decision**: Use Playwright (`@playwright/test`) as the browser-driving and network-interception layer.
- **Rationale**: The feature requires (a) driving a real browser to render React + Leaflet, (b) capturing page content/console errors/network outcomes as evidence (FR-006), and (c) intercepting and mocking HTTP responses at the browser/network layer (FR-008). Playwright provides `page.route()` for request interception, robust auto-waiting, headed/headless modes, tracing/screenshots for evidence, and is agent-friendly (FR-014/SC-007). The existing MCP/Copilot browser tooling is Playwright-based, so an agent can drive the same primitives.
- **Alternatives considered**:
  - *vitest + jsdom*: not a real browser; cannot render Leaflet tiles or validate true network behavior. Already used for unit tests and kept as-is.
  - *Cypress*: viable but heavier, weaker multi-tab/network mocking ergonomics, and less aligned with the agent's existing Playwright primitives.
  - *Selenium*: more boilerplate, weaker built-in interception/evidence capture.

## Decision 2: Reaching protected pages — reuse existing bypass + localStorage seeding

- **Decision**: Reuse the existing backend `DEV_AUTH_BYPASS` setting (authenticates as the first user) and seed the frontend auth state directly into `localStorage` (`access_token`, `user_id`, `display_name`) before navigation.
- **Rationale**: Constitution Principle IV (reuse, no new auth mechanism). The frontend persists auth in `localStorage`; pre-seeding it prevents redirect-to-login (FR-003). The backend bypass returns a real user row so protected endpoints behave normally (FR-002).
- **Alternatives considered**:
  - *Minting a real JWT/session in the harness*: rejected — reintroduces token handling the feature explicitly avoids, and auth/session changes are out of scope (FR-012).
  - *Completing OAuth headlessly*: rejected — depends on Strava, not automatable/deterministic.

## Decision 3: Determinism guarantee — isolated verification DB + frozen PostGIS snapshot

- **Decision**: Run against a dedicated `pacman_verify` PostgreSQL/PostGIS database, separate from the dev `pacman` DB. Street/neighborhood data comes from a frozen, locally-generated (gitignored, not committed) `pg_dump` snapshot of real Seattle data; the demo user + sample activities/coverage are layered on top at seed time.
- **Rationale**: The bypass returns the *first* user; an isolated DB containing only the demo user makes that deterministic (FR-004a). A frozen snapshot avoids non-deterministic live OSM downloads (FR-004b) and, being PostGIS-native, keeps coverage/geometry math identical to production (FR-004c). The existing SQLite `benchmark-seattle.db` and OSM cache JSONs are NOT used as the baseline because coverage math depends on PostGIS behavior.
- **Snapshot mechanics**: Build once via `pg_dump` of a freshly loaded Seattle dataset (streets + neighborhoods + city), excluding any user/activity tables so no real private data is captured (FR-004d). Restore via `pg_restore`/`psql` into `pacman_verify`. Store the artifact under the feature's `snapshot/` folder (or document an external pointer if size is prohibitive).
- **Alternatives considered**:
  - *Live OSMnx download at seed time*: rejected — non-deterministic (upstream OSM edits, network/version variability).
  - *SQLite benchmark DB*: rejected — not PostGIS; coverage math would diverge from production.
  - *Sharing the dev DB*: rejected — "first user" could resolve to real dev data (non-deterministic) and mutate it.

## Decision 4: Forced error-state UI — browser/network-layer interception

- **Decision**: Reproduce error-state UX (401 session-expired, 503/OSRM-unavailable, empty/NOT_FOUND) by intercepting at the browser layer with Playwright `page.route()`, returning a synthetic status/body. The real backend is unchanged.
- **Rationale**: Proves the frontend's error-handling/UX for a given response without backend test seams (FR-008). Keeps Principle I intact — product code's service boundary is untouched.
- **Alternatives considered**:
  - *Backend fault-injection flags/endpoints*: rejected — adds product surface area and risk; the spec scopes interception to the browser layer.

## Decision 5: Launcher + iteration model — thin launcher, warm fast-reset default, clean full bring-up on demand

- **Decision**: Provide a thin launcher (`infra/verify-up.ps1`) bringing up `pacman_verify`, the backend with `DEV_AUTH_BYPASS=1`, and the frontend. Default loop keeps services warm and uses a fast data-only reset (`verify-reset.ps1`) between runs. A clean full bring-up (`verify-clean.ps1`) rebuilds the DB from the snapshot and starts services fresh for a final pre-push check.
- **Rationale**: Warm reuse keeps back-to-back iteration fast (SC-001/SC-002); clean bring-up catches startup/migration/schema regressions warm reuse would miss (FR-019). Full automatic teardown is out of scope (FR-016).
- **Warm-state leakage to clear on reset (FR-018)** — confirmed in code:
  - `app.services.routing._osrm_available` — module-global OSRM availability cache; reset to `None` (or call `check_osrm_available(force=True)`).
  - `clear_active_sync_jobs()` in the sync service — in-process active sync-job tracking; call to clear.
  - DB run-accumulated rows (e.g., generated route suggestions) — truncated and reseeded to baseline.
- **Alternatives considered**:
  - *Always clean bring-up*: rejected — too slow for tight iteration (violates SC-001/SC-002 intent).
  - *Always warm*: rejected — misses startup/schema regressions; stale after impactful changes.
  - *Full lifecycle orchestration with auto-teardown*: rejected — out of scope; over-engineering (Principle IV).

## Decision 6: Bypass safety posture — existing CRITICAL log only

- **Decision**: Rely on the existing CRITICAL-level log emitted when the bypass authenticates a request, plus default-off configuration. No startup fail-safe or in-app banner is added.
- **Rationale**: Matches the clarified scope (FR-009/FR-010). The bypass is local-only and never enabled in shared/deployed environments (SC-006), so visibility via the existing log + developer discipline is sufficient.
- **Alternatives considered**:
  - *Startup hard-block when env != local*: rejected — out of scope; adds product complexity beyond the feature's intent.
  - *In-app banner*: rejected — out of scope; not required for local verification.

## Decision 7: Seed/reset scripts — Python under existing `backend/app/scripts/`, tested with pytest

- **Decision**: Implement `seed_verification.py`, `reset_verification.py`, and `snapshot_verification.py` as Python modules following the existing `load_cities.py` pattern (SQLAlchemy session, GeoAlchemy2). Cover seed/reset with offline pytest unit tests (Principle II).
- **Rationale**: Consistency with existing tooling and the constitution's Test-First and code-style standards (ruff). Seeding demo activities/coverage uses the existing ORM models (`User`, `Activity`, `CoverageSnapshot`, etc.).
- **Alternatives considered**:
  - *Raw SQL fixtures*: rejected — bypasses ORM validation and drifts from existing patterns.

---

## Summary of resolved clarifications

| # | Question | Resolution |
|---|----------|------------|
| 1 | Bypass → demo user determinism | Isolated `pacman_verify` DB with only the demo user |
| 2 | Dataset depth & source | Frozen locally-generated (gitignored) PostGIS snapshot of real Seattle + layered demo user/activities/coverage |
| 3 | Bypass leak safety | Existing CRITICAL log only; default off |
| 4 | Forced error responses | Browser/network-layer interception (Playwright `page.route`) |
| 5 | Launch & fast iteration | Thin launcher; warm + fast data-only reset default; clean full bring-up on demand |

No unresolved unknowns. Ready for Phase 1 design.
