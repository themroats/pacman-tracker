# Implementation Plan: Application Stability & Hardening

**Branch**: `002-app-stability-hardening` | **Date**: 2026-03-14 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-app-stability-hardening/spec.md`

## Summary

Harden the existing Pac-Man Tracker application by fixing silent error paths, enforcing per-user data isolation on all API endpoints, making the Strava sync lifecycle resilient to failures/restarts, adding input validation, and improving frontend loading/error states with toast notifications. This is a stability pass — no new features, only making existing functionality work correctly and reliably.

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.6 (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, GeoAlchemy2, Shapely, React 18.3, Zustand, Leaflet/React-Leaflet
**Storage**: SQLite + SpatiaLite (`./data/pacman.db`)
**Testing**: pytest + pytest-asyncio (backend), Vitest + React Testing Library (frontend)
**Target Platform**: Linux Docker container (backend), Static web app (frontend)
**Project Type**: Web application (FastAPI backend + React SPA frontend)
**Performance Goals**: Coverage queries ≤2 DB queries regardless of neighborhood count; auth lookup O(1) vs current O(n)
**Constraints**: Single-process deployment (SQLite); B1 App Service tier (1 vCPU, 1.75 GB RAM)
**Scale/Scope**: Small-scale (<100 users); 5 pages; ~30 API endpoints across 8 routers

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. API-First Design** | PASS | All changes go through existing REST endpoints; no new external API calls added. Frontend continues to communicate only through backend services. |
| **II. Test-First Development** | PASS | Spec requires integration tests for auth isolation (SC-002), duplicate imports (SC-004), and query counts (SC-007). Existing test structure (`backend/tests/unit/`, `integration/`, `contract/`) is retained. |
| **III. Data Privacy by Design** | PASS | Core goal of this feature: enforce per-user data isolation (FR-005), maintain encrypted token storage, fix auth gaps. Improves compliance with this principle. |
| **IV. Simplicity & Incremental Delivery** | PASS | No new architectural patterns introduced. Changes are scoped to existing files — fixing catch blocks, adding auth dependencies, adding validation. No new libraries beyond a toast notification component. |
| **Technology Standards** | PASS | Python 3.12+, FastAPI, React 18+, SpatiaLite — all unchanged. Code style enforcement via ruff (backend) and ESLint (frontend) retained. |
| **Development Workflow** | PASS | Work on feature branch `002-app-stability-hardening`; PR required for merge to main. |

**Gate Result**: ALL PASS — proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/002-app-stability-hardening/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/             # Route handlers — auth fixes, error handling, validation
│   │   ├── activities.py
│   │   ├── admin.py
│   │   ├── auth.py
│   │   ├── cities.py
│   │   ├── coverage.py
│   │   ├── deps.py      # Auth dependency — O(1) lookup fix
│   │   ├── progress.py  # Remove hardcoded user ID
│   │   ├── routes.py    # Input validation, OSRM health check
│   │   ├── sync.py      # Sync lifecycle state machine
│   │   └── webhook.py   # Non-200 on failure
│   ├── models/          # Status enum enforcement, FK constraints
│   ├── schemas/         # Validation bounds (coordinates, distance)
│   ├── services/        # Error logging, sync recovery, import deduplication
│   ├── config.py
│   ├── database.py      # FK pragma, SpatiaLite error handling
│   └── main.py          # Stale sync recovery on startup
└── tests/
    ├── unit/
    ├── integration/     # Multi-user isolation tests
    └── contract/

frontend/
├── src/
│   ├── api/
│   │   └── client.ts    # Error extraction, toast integration
│   ├── components/      # Toast provider, loading states
│   ├── hooks/           # Error-aware data hooks
│   ├── pages/           # Replace silent catches, add loading/error UI
│   ├── store/
│   │   └── index.ts     # Toast state management
│   └── types/
└── tests/
    ├── api/
    └── components/
```

**Structure Decision**: Existing web application layout (separate `backend/` and `frontend/` directories) is retained. All changes modify existing files — no new directories created. The only new component is a toast notification system in the frontend.

## Complexity Tracking

No violations — no new patterns or abstractions introduced.
