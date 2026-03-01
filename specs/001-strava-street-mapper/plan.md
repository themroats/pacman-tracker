# Implementation Plan: Strava Street Mapper

**Branch**: `001-strava-street-mapper` | **Date**: 2026-02-28 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-strava-street-mapper/spec.md`

## Summary

Build a web application that imports a user's Strava activities via OAuth2, displays GPS routes on an interactive Leaflet map, compares traces against OpenStreetMap street networks to calculate per-neighborhood coverage percentages, and generates route suggestions (via OSRM) that prioritize untraveled streets. The backend is Python/FastAPI with SpatiaLite for geospatial storage; the frontend is React 18+/TypeScript with react-leaflet.

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x (frontend)  
**Primary Dependencies**: FastAPI, Uvicorn, Shapely, GeoPandas, OSMnx, react-leaflet, OSRM  
**Storage**: SQLite + SpatiaLite (development); PostgreSQL + PostGIS (future production)  
**Testing**: pytest (backend), Vitest + React Testing Library (frontend)  
**Target Platform**: Web browser (desktop-first, responsive); local development server  
**Project Type**: Web application (SPA frontend + REST API backend)  
**Performance Goals**: Map renders with up to 500 activity overlays at 30+ fps; street coverage calculation completes in <5s for a city-sized network  
**Constraints**: Strava API rate limits (100 requests/15 min for short-term, 1000/day); SpatiaLite single-writer; OSM data download size per city (~50-200 MB)  
**Scale/Scope**: Single user (local-first), 5 launch cities, ~5-10 screens, up to 2000 activities

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. API-First Design | PASS | All functionality exposed via FastAPI REST endpoints; Strava integration behind dedicated service; OpenAPI auto-generated; React consumes only backend API |
| II. Test-First Development | PASS | pytest for backend geo logic + Strava contract tests with recorded responses; Vitest for frontend; acceptance tests per user story |
| III. Data Privacy by Design | PASS | Strava OAuth2 only (no passwords); tokens encrypted at rest; minimum scopes (activity:read); data deletion path planned |
| IV. Simplicity & Incremental Delivery | PASS | 4 stories deliverable as independent vertical slices; P1 is map + activities before any gamification; no speculative patterns |
| Technology Standards | PASS | Python 3.12+/FastAPI, React 18+/TypeScript/Vite, react-leaflet, Shapely/GeoPandas/OSMnx, SQLite+SpatiaLite (constitution allows for local dev) |
| Development Workflow | PASS | Feature branches, PR with tests, ruff + ESLint/Prettier enforced |

**Gate result**: ALL PASS — proceed to Phase 0.

**Note on SQLite/SpatiaLite**: Constitution lists PostgreSQL+PostGIS as primary with "SQLite + SpatiaLite acceptable for local development." Since hosting is deferred and this is local-first, SpatiaLite is compliant. The data model will be designed to be portable to PostGIS.

## Project Structure

### Documentation (this feature)

```text
specs/001-strava-street-mapper/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (API contracts)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Settings, environment variables
│   ├── database.py          # SpatiaLite/PostGIS connection + session
│   ├── models/              # SQLAlchemy + GeoAlchemy2 ORM models
│   │   ├── user.py
│   │   ├── activity.py
│   │   ├── street.py
│   │   ├── coverage.py
│   │   └── city.py
│   ├── services/            # Business logic
│   │   ├── strava.py        # Strava API client + OAuth
│   │   ├── importer.py      # Activity import pipeline
│   │   ├── coverage.py      # GPS-to-street matching + coverage calc
│   │   ├── routing.py       # OSRM integration + route suggestion
│   │   └── streets.py       # OSMnx street network management
│   ├── api/                 # FastAPI routers
│   │   ├── auth.py          # OAuth endpoints
│   │   ├── activities.py    # Activity CRUD + filters
│   │   ├── coverage.py      # Coverage queries
│   │   ├── routes.py        # Route suggestion endpoints
│   │   └── progress.py      # Stats + milestones
│   └── schemas/             # Pydantic request/response models
│       ├── activity.py
│       ├── coverage.py
│       ├── route.py
│       └── user.py
├── tests/
│   ├── unit/                # Shapely/GeoPandas logic tests
│   ├── contract/            # Strava API recorded responses
│   └── integration/         # Full API endpoint tests
├── pyproject.toml
└── requirements.txt

frontend/
├── src/
│   ├── App.tsx
│   ├── main.tsx
│   ├── api/                 # API client (typed fetch wrappers)
│   │   └── client.ts
│   ├── components/          # Reusable UI components
│   │   ├── Map/             # Leaflet map wrapper + layers
│   │   ├── ActivityList/
│   │   ├── CoverageDashboard/
│   │   ├── RouteSuggestion/
│   │   └── ProgressTimeline/
│   ├── pages/               # Route-level page components
│   │   ├── HomePage.tsx
│   │   ├── MapPage.tsx
│   │   ├── CoveragePage.tsx
│   │   ├── RoutePage.tsx
│   │   └── ProgressPage.tsx
│   ├── hooks/               # Custom React hooks
│   ├── types/               # TypeScript type definitions
│   └── utils/               # Helpers, formatters
├── tests/
│   └── components/          # Vitest + RTL component tests
├── index.html
├── vite.config.ts
├── tsconfig.json
└── package.json
```

**Structure Decision**: Web application pattern (Option 2) — separate `backend/` and `frontend/` directories with independent test suites, matching constitution requirement for isolated test runs. Backend follows FastAPI conventions with `app/` package; frontend follows Vite/React conventions.

## Complexity Tracking

> No constitution violations — table not needed.
