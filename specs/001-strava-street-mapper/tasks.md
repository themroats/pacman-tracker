# Tasks: Strava Street Mapper

**Input**: Design documents from `/specs/001-strava-street-mapper/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Not explicitly requested in the feature specification. Test tasks are omitted.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `backend/app/`, `backend/tests/`
- **Frontend**: `frontend/src/`, `frontend/tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, backend + frontend scaffolding, tooling

- [ ] T001 Create project directory structure per plan.md (`backend/`, `frontend/`, folder trees)
- [ ] T002 Initialize Python backend with pyproject.toml and requirements.txt in `backend/` (FastAPI, Uvicorn, SQLAlchemy, GeoAlchemy2, Shapely, GeoPandas, OSMnx, httpx, cryptography, python-dotenv)
- [ ] T003 [P] Initialize React frontend with Vite + TypeScript in `frontend/` (react-leaflet, leaflet, zustand, react-router-dom)
- [ ] T004 [P] Configure backend linting/formatting: ruff config in `backend/pyproject.toml`
- [ ] T005 [P] Configure frontend linting/formatting: ESLint + Prettier config in `frontend/`
- [ ] T006 [P] Create backend `.env.example` with all required env vars in `backend/.env.example`
- [ ] T007 [P] Create frontend `.env.example` with VITE_API_URL in `frontend/.env.example`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T008 Implement app configuration and settings management in `backend/app/config.py` (Pydantic BaseSettings, Strava credentials, DB URL, secret key, OSRM URL)
- [ ] T009 Implement SpatiaLite database connection, session management, and SpatiaLite extension loading in `backend/app/database.py`
- [ ] T010 [P] Create User ORM model in `backend/app/models/user.py` (all fields per data-model.md, encrypted token fields, sync_status enum)
- [ ] T011 [P] Create City ORM model in `backend/app/models/city.py` (boundary geometry, projected_crs, cached counts)
- [ ] T012 [P] Create Neighborhood ORM model in `backend/app/models/neighborhood.py` (boundary geometry, FK to City, cached counts)
- [ ] T013 [P] Create StreetSegment ORM model in `backend/app/models/street.py` (geometry, osm fields, FK to City/Neighborhood, length_meters)
- [ ] T014 Create database initialization script with table creation and spatial indexes in `backend/app/scripts/init_db.py`
- [ ] T015 [P] Create Pydantic schemas for User (request/response) in `backend/app/schemas/user.py`
- [ ] T016 [P] Implement error handling middleware and standard error response format in `backend/app/main.py`
- [ ] T017 Implement FastAPI app entry point with CORS, router registration, and lifespan events in `backend/app/main.py`
- [ ] T018 [P] Implement token encryption/decryption utility for Strava tokens in `backend/app/services/crypto.py`
- [ ] T019 Create city data loader script (OSMnx street download, neighborhood boundary import, SpatiaLite bulk insert) in `backend/app/scripts/load_cities.py`
- [ ] T020 [P] Create TypeScript type definitions matching API contracts in `frontend/src/types/api.ts`
- [ ] T021 [P] Create typed API client with fetch wrappers and error handling in `frontend/src/api/client.ts`
- [ ] T022 Create Zustand store skeleton (auth state, activities, filters, coverage, selected city) in `frontend/src/store/index.ts`
- [ ] T023 [P] Create base Leaflet Map component with CartoDB Positron tiles and `preferCanvas` in `frontend/src/components/Map/MapView.tsx`
- [ ] T024 Implement React Router with page shell components (Home, Map, Coverage, Route, Progress) in `frontend/src/App.tsx`

**Checkpoint**: Foundation ready — database initialized, city data loadable, backend running, frontend scaffolded with map component. User story implementation can now begin.

---

## Phase 3: User Story 1 — Connect Strava & View Exercise History (Priority: P1) 🎯 MVP

**Goal**: User connects Strava account, all GPS-traced activities are imported and displayed as route overlays on the interactive Leaflet map with filtering and detail views.

**Independent Test**: Connect a Strava account, verify activities import and appear as colored polylines on the map. Click a route to see details. Filter by type/date.

### Backend — US1

- [ ] T025 [P] [US1] Create Activity ORM model in `backend/app/models/activity.py` (all fields per data-model.md, gps_trace geometry, import_status state machine)
- [ ] T026 [P] [US1] Create Pydantic schemas for Activity (list response, detail response, GeoJSON feature) in `backend/app/schemas/activity.py`
- [ ] T027 [US1] Implement Strava OAuth service: authorization URL generation, token exchange, token refresh in `backend/app/services/strava.py`
- [ ] T028 [US1] Implement auth API router: `GET /auth/strava`, `GET /auth/strava/callback`, `POST /auth/logout` in `backend/app/api/auth.py`
- [ ] T029 [US1] Implement Strava activity fetcher: paginated list fetch, detail+polyline fetch, GPS stream fetch in `backend/app/services/strava.py`
- [ ] T030 [US1] Implement activity import pipeline: two-phase import (polyline first, streams second), deduplication, rate-limit handling in `backend/app/services/importer.py`
- [ ] T031 [US1] Implement sync API router: `GET /sync/status`, `POST /sync/trigger` in `backend/app/api/sync.py`
- [ ] T032 [US1] Implement activities API router: `GET /activities` (with filters), `GET /activities/{id}`, `GET /activities/{id}/geojson`, `GET /activities/geojson` in `backend/app/api/activities.py`

### Frontend — US1

- [ ] T033 [P] [US1] Create HomePage with "Connect with Strava" button and OAuth redirect in `frontend/src/pages/HomePage.tsx`
- [ ] T034 [P] [US1] Create auth callback handler page (process OAuth code, store session, redirect to map) in `frontend/src/pages/AuthCallbackPage.tsx`
- [ ] T035 [US1] Implement auth API methods (strava login, callback, logout) in `frontend/src/api/client.ts`
- [ ] T036 [US1] Add auth state management to Zustand store (user session, login/logout actions) in `frontend/src/store/index.ts`
- [ ] T037 [US1] Implement activity route overlay layer: render GeoJSON FeatureCollection as colored Polylines on map in `frontend/src/components/Map/ActivityLayer.tsx`
- [ ] T038 [US1] Implement activity click handler with detail popup (name, date, distance, duration, pace) in `frontend/src/components/Map/ActivityPopup.tsx`
- [ ] T039 [US1] Implement activity filter panel (sport type dropdown, date range picker, distance range) in `frontend/src/components/ActivityList/FilterPanel.tsx`
- [ ] T040 [US1] Implement sync status indicator component (importing/syncing progress, activity count) in `frontend/src/components/SyncStatus.tsx`
- [ ] T041 [US1] Wire MapPage to fetch activities GeoJSON, apply filters, render ActivityLayer + FilterPanel in `frontend/src/pages/MapPage.tsx`

**Checkpoint**: User Story 1 complete — user can connect Strava, import activities, see routes on map, filter by type/date, click for details. MVP delivered.

---

## Phase 4: User Story 2 — Street Coverage Dashboard (Priority: P2)

**Goal**: User selects a city or neighborhood to see streets color-coded (green = traveled, grey = untraveled) with a coverage percentage dashboard broken down by neighborhood.

**Independent Test**: Select a neighborhood, verify streets are correctly classified based on imported activities, confirm coverage percentage matches manual count.

### Backend — US2

- [ ] T042 [P] [US2] Create UserStreetCoverage ORM model in `backend/app/models/coverage.py` (coverage_ratio, is_traveled, first_traveled_at, FK relationships)
- [ ] T043 [P] [US2] Create Pydantic schemas for Coverage (city summary, neighborhood detail, street GeoJSON feature) in `backend/app/schemas/coverage.py`
- [ ] T044 [US2] Implement GPS-to-street matching service: buffer GPS trace by 15m, intersect with street segments, compute coverage_ratio, update UserStreetCoverage in `backend/app/services/coverage.py`
- [ ] T045 [US2] Integrate coverage computation into import pipeline: trigger matching after activity GPS streams are imported in `backend/app/services/importer.py`
- [ ] T046 [US2] Implement coverage API router: `GET /coverage/city/{city_id}`, `GET /coverage/neighborhood/{neighborhood_id}`, `GET /coverage/neighborhood/{neighborhood_id}/streets`, `GET /coverage/city/{city_id}/streets` in `backend/app/api/coverage.py`
- [ ] T047 [P] [US2] Implement cities API router: `GET /cities`, `GET /cities/{city_id}/neighborhoods`, `GET /cities/{city_id}/neighborhoods/{neighborhood_id}/boundary` in `backend/app/api/cities.py`

### Frontend — US2

- [ ] T048 [P] [US2] Create street coverage map layer: render street GeoJSON with color coding (green/grey) via style function in `frontend/src/components/Map/StreetCoverageLayer.tsx`
- [ ] T049 [P] [US2] Create neighborhood boundary layer: render neighborhood polygons with click-to-select behavior in `frontend/src/components/Map/NeighborhoodLayer.tsx`
- [ ] T050 [P] [US2] Create CoverageDashboard component: city-wide percentage, per-neighborhood breakdown table with percentages in `frontend/src/components/CoverageDashboard/CoverageSummary.tsx`
- [ ] T051 [US2] Create city/neighborhood selector component (dropdown or map click) with flyToBounds on selection in `frontend/src/components/CoverageDashboard/AreaSelector.tsx`
- [ ] T052 [US2] Wire CoveragePage to fetch street data + coverage stats, render StreetCoverageLayer + NeighborhoodLayer + CoverageDashboard in `frontend/src/pages/CoveragePage.tsx`
- [ ] T053 [US2] Add coverage state (selected city, selected neighborhood, coverage data) to Zustand store in `frontend/src/store/index.ts`

**Checkpoint**: User Story 2 complete — user can see color-coded streets, neighborhood-level coverage percentages, and a city-wide dashboard. Works independently from US3/US4.

---

## Phase 5: User Story 3 — Route Suggestions for Unmapped Streets (Priority: P3)

**Goal**: User specifies a starting point and distance, system generates a route prioritizing untraveled streets via OSRM, displayed on the map with untraveled segments highlighted.

**Independent Test**: Request a 5km route suggestion for a partially-covered neighborhood, verify route prioritizes untraveled streets and is within 10% of requested distance.

### Backend — US3

- [ ] T054 [P] [US3] Create RouteSuggestion and RouteSuggestionSegment ORM models in `backend/app/models/route.py` (all fields per data-model.md)
- [ ] T055 [P] [US3] Create Pydantic schemas for route suggestion (request body, response with geometry + segments) in `backend/app/schemas/route.py`
- [ ] T056 [US3] Implement OSRM client service: `/nearest`, `/trip`, `/route` endpoints, GeoJSON response parsing in `backend/app/services/routing.py`
- [ ] T057 [US3] Implement route suggestion algorithm: query untraveled streets, select waypoint midpoints, call OSRM `/trip`, iterate to match target distance in `backend/app/services/routing.py`
- [ ] T058 [US3] Handle "100% covered" case: detect full coverage, find neighboring neighborhoods with lowest coverage, return suggestion in `backend/app/services/routing.py`
- [ ] T059 [US3] Implement routes API router: `POST /routes/suggest`, `GET /routes/history` in `backend/app/api/routes.py`

### Frontend — US3

- [ ] T060 [P] [US3] Create route suggestion form component (starting point picker, distance input, neighborhood dropdown) in `frontend/src/components/RouteSuggestion/RouteForm.tsx`
- [ ] T061 [P] [US3] Create route display layer: render suggested route polyline with untraveled segments highlighted in contrasting color in `frontend/src/components/Map/RouteLayer.tsx`
- [ ] T062 [US3] Create route detail panel: total distance, untraveled ratio, segment list with street names in `frontend/src/components/RouteSuggestion/RouteDetail.tsx`
- [ ] T063 [US3] Wire RoutePage to request suggestion, display RouteLayer + RouteForm + RouteDetail in `frontend/src/pages/RoutePage.tsx`

**Checkpoint**: User Story 3 complete — user can generate route suggestions that prioritize untraveled streets, view them on the map, and see segment details.

---

## Phase 6: User Story 4 — Progress Tracking Over Time (Priority: P4)

**Goal**: User views coverage milestones (25%, 50%, 75%, 100%), a progress timeline chart, and overall statistics (total streets, distance, activity count, city coverage).

**Independent Test**: Verify milestones are recorded with correct dates, timeline chart reflects historical growth, and stats page shows accurate totals.

### Backend — US4

- [ ] T064 [P] [US4] Create CoverageSnapshot ORM model in `backend/app/models/coverage.py` (milestone tracking, snapshot_date, coverage_percentage per area)
- [ ] T065 [P] [US4] Create Pydantic schemas for progress (timeline entry, milestone, overall stats) in `backend/app/schemas/progress.py`
- [ ] T066 [US4] Implement snapshot service: record daily coverage snapshots, detect milestones (25/50/75/100%), associate timestamps in `backend/app/services/progress.py`
- [ ] T067 [US4] Integrate snapshot creation into coverage computation pipeline: trigger after coverage recalculation in `backend/app/services/coverage.py`
- [ ] T068 [US4] Implement progress API router: `GET /progress/city/{city_id}` (timeline + milestones), `GET /progress/stats` (overall stats) in `backend/app/api/progress.py`

### Frontend — US4

- [ ] T069 [P] [US4] Create progress timeline chart component (line chart of coverage % over time, milestone markers) in `frontend/src/components/ProgressTimeline/TimelineChart.tsx`
- [ ] T070 [P] [US4] Create milestone list component (achievement badges with dates for each neighborhood) in `frontend/src/components/ProgressTimeline/MilestoneList.tsx`
- [ ] T071 [P] [US4] Create overall stats component (total unique streets, total distance, activity count, city coverage) in `frontend/src/components/ProgressTimeline/StatsOverview.tsx`
- [ ] T072 [US4] Wire ProgressPage to fetch timeline + milestones + stats, render chart + milestones + stats in `frontend/src/pages/ProgressPage.tsx`

**Checkpoint**: User Story 4 complete — user can track coverage progress over time, see milestones, and view overall statistics.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T073 [P] Add navigation header with links to Map, Coverage, Route, Progress pages in `frontend/src/components/Layout/NavBar.tsx`
- [ ] T074 [P] Implement responsive layout shell (sidebar + map layout, collapsible on mobile) in `frontend/src/components/Layout/AppLayout.tsx`
- [ ] T075 Handle Strava token refresh in auth middleware: auto-refresh expired tokens before API calls in `backend/app/services/strava.py`
- [ ] T076 Handle Strava rate limiting with exponential backoff and user notification in `backend/app/services/importer.py`
- [ ] T077 [P] Add loading states and error boundaries to all frontend pages in `frontend/src/components/common/`
- [ ] T078 [P] Add GPS quality detection: flag activities with significant GPS gaps for user review in `backend/app/services/importer.py`
- [ ] T079 Run quickstart.md validation: verify full setup flow end-to-end
- [ ] T080 [P] Create OSRM Docker Compose configuration for local development in `docker-compose.yml`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational phase completion — BLOCKS US2 (coverage needs activities)
- **US2 (Phase 4)**: Depends on US1 (needs imported activities and GPS traces to compute coverage)
- **US3 (Phase 5)**: Depends on US2 (needs coverage data to identify untraveled streets) + requires OSRM running
- **US4 (Phase 6)**: Depends on US2 (needs coverage computation to generate snapshots/milestones)
- **Polish (Phase 7)**: Can overlap with US3/US4; full completion after all stories done

### User Story Dependencies

- **US1 (P1)**: Foundation only — independent, delivers MVP
- **US2 (P2)**: Requires US1 activities + GPS data to compute street coverage
- **US3 (P3)**: Requires US2 coverage data to identify untraveled streets for routing
- **US4 (P4)**: Requires US2 coverage computation to generate snapshots; can run in parallel with US3

### Within Each User Story

- Backend models before services
- Services before API routers
- Backend endpoints before frontend pages that consume them
- Stories complete at checkpoint before dependent stories begin

### Parallel Opportunities

**Phase 1 (Setup)**: T003, T004, T005, T006, T007 all run in parallel  
**Phase 2 (Foundational)**: T010, T011, T012, T013 (models) in parallel; T015, T016, T018 in parallel; T020, T021, T023 in parallel  
**US1 Backend**: T025 + T026 in parallel → T027 → T028 + T029 → T030 → T031 + T032  
**US1 Frontend**: T033 + T034 in parallel; T037 + T038 + T039 + T040 in parallel after T035/T036  
**US2**: T042 + T043 + T047 in parallel → T044 → T045/T046; T048 + T049 + T050 in parallel  
**US3 + US4**: US4 can run in parallel with US3 (independent backend + frontend tracks)

---

## Parallel Example: User Story 1

```bash
# Backend models + schemas in parallel:
Task T025: "Create Activity ORM model in backend/app/models/activity.py"
Task T026: "Create Pydantic schemas for Activity in backend/app/schemas/activity.py"

# Frontend auth + UI components in parallel (after API client wired):
Task T033: "Create HomePage with Connect with Strava button"
Task T034: "Create auth callback handler page"

# Frontend map components in parallel (after store + API wired):
Task T037: "Implement activity route overlay layer"
Task T038: "Implement activity click handler with detail popup"
Task T039: "Implement activity filter panel"
Task T040: "Implement sync status indicator component"
```

---

## Parallel Example: User Story 2

```bash
# Backend models + schemas + cities router in parallel:
Task T042: "Create UserStreetCoverage ORM model"
Task T043: "Create Pydantic schemas for Coverage"
Task T047: "Implement cities API router"

# Frontend map layers in parallel:
Task T048: "Create street coverage map layer"
Task T049: "Create neighborhood boundary layer"
Task T050: "Create CoverageDashboard component"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T007)
2. Complete Phase 2: Foundational (T008–T024)
3. Complete Phase 3: User Story 1 (T025–T041)
4. **STOP and VALIDATE**: Connect Strava, import activities, see routes on map
5. Deploy/demo if ready — this is a usable app

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 → Test independently → **MVP!** (map + activities)
3. Add US2 → Test independently → Coverage dashboard live
4. Add US3 → Test independently → Route suggestions working
5. Add US4 → Test independently → Progress tracking complete
6. Polish → Production-ready

### Key Risk: Strava Rate Limits

The two-phase import strategy (T030) is critical. Phase A (polyline fetch) gets routes on the map fast. Phase B (GPS streams) runs in background for street matching accuracy. Monitor rate limits during T076.
