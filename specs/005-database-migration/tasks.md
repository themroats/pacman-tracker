# Tasks: Database Migration — SQLite to PostgreSQL

**Input**: Design documents from `/specs/005-database-migration/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Exact file paths included in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add PostgreSQL dependencies and configure the project for PostgreSQL

- [x] T001 Add psycopg2-binary, alembic, azure-identity, and testcontainers[postgres] to backend/requirements.txt
- [x] T002 [P] Add PostgreSQL + PostGIS service to docker-compose.yml per research R6 configuration
- [x] T003 [P] Update backend/.env.example with DATABASE_URL=postgresql://pacman:pacman_dev@localhost:5432/pacman

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Rewrite core database layer for PostgreSQL — MUST complete before any user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Rewrite backend/app/database.py to remove all SpatiaLite code (enable_load_extension, _load_spatialite, _enable_foreign_keys, InitSpatialMetaData, _ensure_sqlite_parent_dir) and replace with PostgreSQL engine creation using CREATE EXTENSION IF NOT EXISTS postgis, configurable pool_size/max_overflow, and PostGIS validation at startup per research R1
- [x] T005 Update backend/app/config.py to remove the is_sqlite property, remove sqlite default from database_url, and add pool_size and max_overflow settings with sensible defaults per FR-014
- [x] T006 Rewrite backend/tests/conftest.py to replace in-memory SpatiaLite engine with testcontainers PostgresContainer using postgis/postgis:16-3.4 image, CREATE EXTENSION postgis, and Base.metadata.create_all per research R5
- [x] T007 Replace SpatialIndex R-tree queries in backend/app/services/coverage.py with GeoAlchemy2 ST_Intersects + ST_MakeEnvelope expressions per research R2 migration pattern
- [x] T008 [P] Replace SpatialIndex R-tree queries in backend/app/scripts/load_neighborhoods.py with GeoAlchemy2 ST_Intersects + ST_MakeEnvelope + ST_Within + ST_Centroid expressions per research R2
- [x] T008B [P] Replace SpatialIndex R-tree queries in backend/app/services/routing.py with GeoAlchemy2 ST_Intersects + ST_MakeEnvelope expressions per research R2 (2 occurrences identified in codebase analysis)
- [x] T008C [P] Remove or rewrite backend/app/scripts/init_db.py — eliminate SQLite directory creation, SpatiaLite version detection, and CreateSpatialIndex calls; PostGIS creates GiST indexes automatically via GeoAlchemy2
- [x] T009 Remove hand-written ALTER TABLE migration statements from backend/app/main.py lifespan function (access_token_hash and sync_started_at column additions) per FR-012
- [x] T010 Update backend/Dockerfile to remove libsqlite3-mod-spatialite and libsqlite3-0 packages, add libpq-dev and postgresql-client, and change DATABASE_URL default to postgresql:// scheme

**Checkpoint**: Database layer is PostgreSQL-native. All SpatiaLite code removed. Tests run against PostGIS containers.

---

## Phase 3: User Story 1 — Application Runs on a Production-Grade Database (Priority: P1) 🎯 MVP

**Goal**: Application connects to PostgreSQL + PostGIS and all existing features work identically

**Independent Test**: Start the app pointed at a local PostGIS container, run the full test suite, verify all CRUD operations and geospatial queries pass

### Implementation for User Story 1

- [x] T011 [US1] Add startup validation in backend/app/database.py that checks PostgreSQL connection and PostGIS extension availability, failing fast with a clear error message within 10 seconds per FR-010 and SC-008
- [x] T012 [US1] Add connection error handling middleware or exception handler in backend/app/main.py that returns appropriate HTTP error responses when the database is unreachable per FR-011
- [x] T013 [US1] Implement Azure Managed Identity authentication in backend/app/database.py using DefaultAzureCredential from azure-identity to obtain PostgreSQL access tokens when running on Azure per research R3 and FR-013
- [x] T014 [US1] Run the existing test suite against PostgreSQL via testcontainers and fix any remaining SQLite-specific test assumptions or query patterns per SC-001
- [x] T015 [US1] Verify all GeoAlchemy2 spatial operations (ST_Intersects, ST_Within, ST_Centroid, ST_Buffer, to_shape, from_shape) produce correct results against PostGIS by running existing geospatial tests per FR-004 and SC-003
- [ ] T015B [US1] Run a concurrency validation test with 50 simulated concurrent read requests and 10 concurrent background sync operations against PostgreSQL, verifying no errors or timeouts per SC-002

**Checkpoint**: Application runs on PostgreSQL. All existing tests pass. Geospatial queries return correct results. Concurrency targets validated. MVP is functional.

---

## Phase 4: User Story 4 — City & Neighborhood Bootstrap Works on PostgreSQL (Priority: P2)

**Goal**: Auto-bootstrap seeds cities, street segments, and neighborhoods correctly on a fresh PostgreSQL database

**Independent Test**: Start app against empty PostGIS database with auto_load_cities_on_empty_db=true, wait for bootstrap to complete, verify all spatial data is present and queryable

### Implementation for User Story 4

- [x] T016 [US4] Verify backend/app/scripts/load_cities.py works against PostgreSQL — ensure WKT geometry inserts with SRID=4326 and bulk session.add_all() complete without errors on PostGIS
- [x] T017 [US4] Verify backend/app/scripts/load_neighborhoods.py works against PostgreSQL — confirm the rewritten spatial queries from T008 correctly assign streets to neighborhoods via ST_Within + ST_Centroid
- [x] T018 [US4] Verify backend/app/services/city_bootstrap.py background thread bootstrap completes on PostgreSQL without database lock contention — test concurrent API requests during bootstrap return "loading" status without errors
- [x] T019 [US4] Verify admin bootstrap endpoints in backend/app/api/admin.py (POST /admin/bootstrap/cities, POST /admin/bootstrap/neighborhoods) trigger and complete successfully against PostgreSQL
- [x] T020 [US4] Run end-to-end bootstrap validation: start app against empty PostGIS, wait for bootstrap, then query cities, neighborhoods, and street segments via API to confirm all geometries are spatially indexed and queryable per SC-004 and SC-005

**Checkpoint**: Bootstrap works on PostgreSQL. Fresh database is fully seeded with spatial data.

---

## Phase 5: User Story 2 — Schema Changes Are Managed Systematically (Priority: P2)

**Goal**: Alembic manages all schema changes with versioned, transactional migrations

**Independent Test**: Create a migration, apply it to a test database, verify schema, roll back, verify original schema restored

### Implementation for User Story 2

- [x] T021 [US2] Create backend/alembic.ini with PostgreSQL connection string reference and backend/alembic/ directory structure (env.py, script.py.mako, versions/) per research R4
- [x] T022 [US2] Configure backend/alembic/env.py to import app.database.Base.metadata and app.models, configure GeoAlchemy2 spatial column rendering, and use the DATABASE_URL from app.config
- [x] T023 [US2] Generate initial baseline migration in backend/alembic/versions/001_initial_schema.py using alembic revision --autogenerate capturing all 9 tables with PostGIS geometry columns, indexes, and constraints from data-model.md
- [x] T024 [US2] Verify alembic upgrade head creates all tables on a fresh PostgreSQL database and produces a schema identical to Base.metadata.create_all per SC-007
- [x] T025 [US2] Verify alembic downgrade -1 rolls back the initial migration cleanly per FR-007
- [x] T025B [US2] Verify concurrent alembic upgrade head from two processes — confirm Alembic advisory lock prevents double-apply and second process waits or exits cleanly per edge case (multiple instances starting simultaneously)
- [x] T026 [US2] Update backend/app/main.py lifespan to run alembic upgrade head on startup (replacing Base.metadata.create_all) so migrations apply automatically on deployment

**Checkpoint**: Schema changes are versioned. Migrations apply and roll back correctly. No more hand-written ALTER TABLE.

---

## Phase 6: User Story 3 — Local Development Remains Simple (Priority: P3)

**Goal**: One-command local setup with Docker Compose, documented in quickstart

**Independent Test**: Clone repo, follow quickstart steps, verify app starts and tests pass within 5 minutes

### Implementation for User Story 3

- [x] T027 [US3] Update backend/README.md with PostgreSQL setup instructions referencing docker compose up db, alembic upgrade head, and the new DATABASE_URL configuration
- [x] T028 [US3] Validate the quickstart.md workflow end-to-end: docker compose up db, pip install, alembic upgrade head, uvicorn start, confirm app serves requests against local PostGIS per SC-006
- [x] T029 [US3] Add a docker compose healthcheck-based wait script or document the pg_isready check so developers know when the database is ready before running alembic

**Checkpoint**: New developer can set up and run the app locally in under 5 minutes.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Deployment, cleanup, and documentation

- [x] T030 [P] Update infra/deploy-prod.ps1 to provision Azure Database for PostgreSQL Flexible Server with PostGIS extension, configure managed identity access, and update the app service DATABASE_URL setting
- [x] T031 [P] Remove all SQLite/SpatiaLite references from the codebase: delete backend/data/ directory reference in .gitignore, remove libspatialite-5.1.0/ from workspace if no longer needed, clean up any remaining sqlite:// URL references
- [x] T032 [P] Update the root README.md to reflect PostgreSQL as the database and reference the quickstart for local setup
- [ ] T033 Run full integration test: deploy to a staging environment with Azure PostgreSQL Flexible Server, run bootstrap, verify all API endpoints return correct data per SC-001 through SC-008 *(deferred: requires Azure access)*
- [x] T034 [P] Update .specify/memory/constitution.md Technology Standards to remove the SQLite clause, reflecting PostgreSQL + PostGIS as the sole database for all environments

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 (T001 must complete first; T002/T003 are parallel)
- **User Story 1 (Phase 3)**: Depends on Phase 2 completion — BLOCKS remaining stories
- **User Story 4 (Phase 4)**: Depends on Phase 3 (needs working PostgreSQL database layer + spatial queries)
- **User Story 2 (Phase 5)**: Depends on Phase 3 (needs working PostgreSQL; can run parallel with Phase 4)
- **User Story 3 (Phase 6)**: Depends on Phases 4 & 5 (Docker Compose + Alembic must both work)
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Foundation only — no dependencies on other stories
- **US4 (P2)**: Depends on US1 (needs the rewritten spatial queries and PostgreSQL database layer)
- **US2 (P2)**: Depends on US1 — can run **parallel with US4** (different files, no overlap)
- **US3 (P3)**: Depends on US2 and US4 (documentation needs Alembic + Docker Compose working)

### Within Each User Story

- Core implementation before integration
- Verification/validation at end of each story

### Parallel Opportunities

Within Phase 1:
```
T001 ──┐
T002 ──┼── all parallel (different files)
T003 ──┘
```

Within Phase 2:
```
T004 ── T005 ── (sequential: config depends on database.py)
T006 ──── (parallel with T004: different file)
T007 ──── T008 (parallel: coverage.py and load_neighborhoods.py are independent)
T009 ──── (parallel with T007: main.py vs services/)
T010 ──── (parallel with T007: Dockerfile vs services/)
```

Phases 4 & 5 can run in parallel:
```
Phase 4 (US4: Bootstrap) ──┐
                           ├── Phase 6 (US3: Dev Setup)
Phase 5 (US2: Alembic)  ──┘
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (dependencies + Docker Compose)
2. Complete Phase 2: Foundational (rewrite database layer, fix spatial queries, migrate tests)
3. Complete Phase 3: User Story 1 (validation, error handling, managed identity, test verification)
4. **STOP and VALIDATE**: All existing tests pass against PostgreSQL. App is functional.
5. Deploy to staging if ready — this is the MVP

### Incremental Delivery

1. Setup + Foundational → Database layer works on PostgreSQL
2. User Story 1 → App runs on PostgreSQL with all features → **MVP!**
3. User Story 4 → Bootstrap seeds fresh database correctly
4. User Story 2 → Schema migrations via Alembic replace manual ALTER TABLE
5. User Story 3 → Developer onboarding documented and validated
6. Polish → Production deployment, cleanup
