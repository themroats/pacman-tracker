# Implementation Plan: Local Browser-Based Verification Harness

**Branch**: `008-browser-verification-harness` | **Date**: 2026-06-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/008-browser-verification-harness/spec.md`

## Summary

Provide a local-only harness that lets a developer or an AI agent drive the running web app in a real browser to confirm a fix works before pushing — without completing real Strava OAuth. It reuses the existing `DEV_AUTH_BYPASS` backend setting (which authenticates as the first user) and the existing frontend localStorage auth state, against a dedicated, isolated verification database seeded from a frozen, locally-generated (gitignored, not committed) PostGIS snapshot of real Seattle street data plus a demo user and sample activities/coverage. A thin launcher brings up the verification DB + backend (bypass on) + frontend; the default loop keeps services warm and does a fast data-only reset between runs, with an on-demand clean full bring-up for a final pre-push check. Forced error-state UI is reproduced by intercepting responses at the browser/network layer (no backend changes). Verification is agent-driven on demand, with a thin reusable scaffold so high-value flows can later be promoted into saved Playwright specs.

## Technical Context

**Language/Version**: Python 3.12+ (backend, seed/reset scripts); TypeScript 5.6 / Node 20 (frontend, Playwright harness)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, GeoAlchemy2, PostGIS; React 18 + Vite; Playwright (`@playwright/test`) — new dev dependency for browser driving and network interception
**Storage**: PostgreSQL 16 + PostGIS 3.4 (dedicated `pacman_verify` database, isolated from dev `pacman` DB); frozen snapshot artifact as a `pg_dump` (custom or plain SQL format)
**Testing**: pytest (seed/reset script unit tests, offline); Playwright (browser verification scaffold + promotable specs); existing vitest unchanged
**Target Platform**: Local developer machine (Windows/macOS/Linux) with Docker Compose for PostGIS
**Project Type**: Web application (existing `backend/` + `frontend/`) plus local tooling/scripts
**Performance Goals**: Reach a protected page in < 1 min from a warm stack (SC-001); a typical verification run yields pass/fail in < 2 min (SC-002); fast data-only reset between back-to-back runs (seconds, not minutes)
**Constraints**: Strictly local; `DEV_AUTH_BYPASS` default off and surfaced via existing CRITICAL log (FR-009/FR-010); deterministic baseline (SC-003) via frozen snapshot + data-only reset; snapshot must contain no real person's private activity data (FR-004d); no new backend API endpoints
**Scale/Scope**: One city (Seattle, ~300k street segments) in the snapshot; one demo user; a handful of sample activities/coverage rows; 3 priority error-state scenarios (401, 503/OSRM-unavailable, empty/NOT_FOUND)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment | Status |
|-----------|------------|--------|
| I. API-First Design | No new API endpoints added; reuses existing bypass and endpoints. Frontend still calls only backend. Forced responses are injected at the test/browser layer, not by bypassing the service boundary in product code. | PASS |
| II. Test-First Development | Seed/reset scripts get failing pytest tests first; the harness itself is a testing tool. Promotable Playwright specs follow red-green where authored. Geospatial math is untouched (snapshot reuses real geometry). | PASS |
| III. Data Privacy by Design | TENSION: bypass disables auth. Mitigated: local-only, default off, CRITICAL log (existing), isolated DB, and snapshot MUST exclude real private activity data (FR-004d). No tokens/passwords introduced. Documented in Complexity Tracking. | PASS (with mitigation) |
| IV. Simplicity & Incremental Delivery | Reuses existing bypass + localStorage auth; adds a thin launcher + seed/reset + one dev dependency (Playwright). Each user story is an independent vertical slice. No new architectural patterns. | PASS |
| Technology Standards | Adds Playwright (proven need: real-browser driving + network interception; no existing dependency provides this). PostGIS snapshot aligns with mandated data store. Ruff/ESLint/Prettier still apply. | PASS |
| Development Workflow | Work on feature branch `008-...`; scripts ship with tests; bypass never enabled in shared/deployed envs. | PASS |

**Result**: PASS. One justified tension (bypass vs. Data Privacy) recorded in Complexity Tracking; all mitigations are existing or in-scope.

## Project Structure

### Documentation (this feature)

```text
specs/008-browser-verification-harness/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── seed-cli.md          # Seed/reset/snapshot CLI contract
│   ├── launcher-cli.md      # Verification launcher CLI contract
│   └── harness-api.md       # Playwright auth/seed/intercept helper contract
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── app/
│   └── scripts/
│       ├── seed_verification.py     # NEW: create demo user + sample activities/coverage in verify DB
│       ├── reset_verification.py    # NEW: fast data-only reset to baseline (truncate + reseed)
│       └── snapshot_verification.py # NEW: build/restore the frozen Seattle PostGIS snapshot
└── tests/
    └── unit/
        ├── test_seed_verification.py    # NEW: seed creates exactly one demo user + expected rows
        └── test_reset_verification.py   # NEW: reset restores baseline, clears accumulated/cached state

frontend/
├── tests/
│   └── e2e/                          # NEW: Playwright harness + promotable specs
│       ├── helpers/
│       │   ├── auth.ts                   # seed localStorage auth state (access_token/user_id/display_name)
│       │   ├── intercept.ts              # browser-layer forced-response helpers
│       │   └── evidence.ts               # capture page content, console errors, network outcomes
│       ├── smoke.protected-pages.spec.ts # P1 example: reach coverage/map without OAuth
│       └── error-states.spec.ts          # P3 examples: 401 / 503 / NOT_FOUND UX
├── playwright.config.ts              # NEW: base URL, project config (headed/headless)
└── package.json                      # MODIFIED: add @playwright/test + scripts

infra/
├── verify-up.ps1                     # NEW: thin launcher (verify DB + backend bypass-on + frontend), warm
├── verify-reset.ps1                  # NEW: fast data-only reset between runs
└── verify-clean.ps1                  # NEW: clean full bring-up (rebuild DB from snapshot, fresh startup)

docker-compose.yml                    # MODIFIED: add isolated verification DB service (or documented reuse)
specs/008-browser-verification-harness/snapshot/   # NEW: frozen Seattle snapshot artifact (or pointer/docs)
```

**Structure Decision**: Web application (existing `backend/` + `frontend/`). New code is additive and isolated: Python seed/reset/snapshot scripts live under the existing `backend/app/scripts/` with tests under `backend/tests/unit/`; the browser harness lives under `frontend/tests/e2e/` with a new `playwright.config.ts`; launcher scripts live under the existing `infra/` directory alongside the current PowerShell helpers. No product/runtime source code paths change; the only backend behavior relied upon (`DEV_AUTH_BYPASS`) already exists.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Auth bypass conflicts with Principle III (Data Privacy by Design) | Reaching protected pages in a browser without real Strava OAuth is the core capability; OAuth cannot be automated locally and depends on an external service | Real-auth-only verification rejected: cannot be agent-driven and is slow/flaky. Mitigations keep it safe: local-only, default off, existing CRITICAL log, isolated DB, and snapshot excludes real private activity data |
| New dev dependency: Playwright | Need real-browser driving plus network-layer response interception (FR-005, FR-006, FR-008); no existing dependency provides this | vitest/jsdom rejected: not a real browser, cannot validate Leaflet map rendering or true network behavior. Manual browser testing rejected: not repeatable or agent-driven |
