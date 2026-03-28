# Implementation Plan: Database Migration — SQLite to PostgreSQL

**Branch**: `005-database-migration` | **Date**: 2026-03-23 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/005-database-migration/spec.md`

## Summary

Replace the SQLite + SpatiaLite database with PostgreSQL + PostGIS as the sole database for all environments. This involves rewriting the database initialization layer, converting SpatiaLite-specific R-tree queries to PostGIS GiST equivalents, introducing Alembic for schema migrations, updating Docker Compose for local development, migrating tests to testcontainers-python, and configuring Azure Managed Identity for production authentication.

## Technical Context

**Language/Version**: Python 3.12+  
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0+, GeoAlchemy2, Alembic, psycopg2-binary, azure-identity, testcontainers-python  
**Storage**: PostgreSQL 16 + PostGIS 3.4 (Azure Database for PostgreSQL Flexible Server in production; Docker container locally)  
**Testing**: pytest + testcontainers[postgres] (PostGIS Docker container per test session)  
**Target Platform**: Azure App Service (Linux container) for production; Docker Compose for local dev  
**Project Type**: Web service (FastAPI backend + React frontend)  
**Performance Goals**: 50 concurrent readers, 10 concurrent background sync workers (SC-002)  
**Constraints**: Azure Managed Identity for production auth; no stored credentials; Docker required for local dev  
**Scale/Scope**: ~300k street segments per city, thousands of activities per user, single-digit application instances

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. API-First Design | PASS | No API contract changes — all endpoints retain the same request/response shapes. Database change is internal. |
| II. Test-First Development | PASS | Tests will be migrated to testcontainers-python (PostGIS Docker). Existing test patterns preserved. Plan includes test infrastructure migration as a prerequisite task. |
| III. Data Privacy by Design | PASS | Tokens remain encrypted at rest. Azure Managed Identity (FR-013) eliminates stored DB credentials — net security improvement. |
| IV. Simplicity & Incremental Delivery | PASS | No new architectural patterns introduced. Alembic is the standard migration tool for SQLAlchemy — not speculative. Each user story is independently deliverable. |
| Technology Standards | NOTE | Constitution says "PostgreSQL with PostGIS for geospatial queries; SQLite + SpatiaLite acceptable for local development." This feature drops SQLite entirely. Constitution update may be warranted post-delivery to remove the SQLite clause. |
| Development Workflow | PASS | All work on feature branch. Tests required for merge. |

**Gate result**: PASS — no violations. The Technology Standards note is informational; the constitution already lists PostgreSQL as the primary data store.

## Project Structure

### Documentation (this feature)

```text
specs/005-database-migration/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output — spatial function mapping, Alembic, testcontainers, etc.
├── data-model.md        # Phase 1 output — entity model with PostgreSQL types
├── quickstart.md        # Phase 1 output — local development setup guide
├── contracts/           # Phase 1 output — no external API changes (internal migration)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (files affected by this feature)

```text
backend/
├── alembic.ini                          # NEW — Alembic configuration
├── Dockerfile                           # MODIFY — replace SpatiaLite deps with PostgreSQL client
├── requirements.txt                     # MODIFY — add psycopg2-binary, alembic, azure-identity, testcontainers
├── alembic/                             # NEW — migration framework
│   ├── env.py                           # Alembic environment (references Base.metadata)
│   ├── script.py.mako                   # Migration template
│   └── versions/
│       └── 001_initial_schema.py        # Baseline migration from current models
├── app/
│   ├── config.py                        # MODIFY — remove is_sqlite property, add pool config
│   ├── database.py                      # MODIFY — rewrite for PostgreSQL (remove SpatiaLite loading)
│   ├── main.py                          # MODIFY — remove hand-written ALTER TABLE, add Alembic auto-migrate
│   ├── services/
│   │   ├── coverage.py                  # MODIFY — replace SpatialIndex R-tree queries
│   │   └── routing.py                   # MODIFY — replace SpatialIndex R-tree queries (2 occurrences)
│   └── scripts/
│       ├── load_neighborhoods.py        # MODIFY — replace SpatialIndex R-tree queries
│       └── init_db.py                   # MODIFY — remove SpatiaLite detection, CreateSpatialIndex calls
├── tests/
│   └── conftest.py                      # MODIFY — replace SpatiaLite engine with testcontainers PostgreSQL
docker-compose.yml                       # MODIFY — add PostgreSQL + PostGIS service
infra/
├── deploy-prod.ps1                      # MODIFY — add Azure PG Flexible Server provisioning
```

**Structure Decision**: Existing web application structure (backend/ + frontend/) is retained. This feature only modifies backend infrastructure — no frontend changes. No new directories except `backend/alembic/` for the migration framework.

## Complexity Tracking

No constitution violations. No complexity justifications required.

## Post-Design Constitution Re-Check

| Principle | Status | Evidence |
|-----------|--------|----------|
| I. API-First Design | PASS | Contracts document confirms no external API changes. |
| II. Test-First Development | PASS | Research R5 defines testcontainers-python approach. Test fixtures migrate cleanly. |
| III. Data Privacy by Design | PASS | Research R3 documents Azure Managed Identity — passwordless, no stored credentials. |
| IV. Simplicity & Incremental Delivery | PASS | Data model is 1:1 with existing schema (no new entities). Alembic, psycopg2, testcontainers are all standard Python ecosystem tools. |
| Technology Standards | PASS | PostgreSQL + PostGIS is already in the constitution. |

**Post-design gate result**: PASS — design artifacts are consistent with constitution principles.
