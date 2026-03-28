# Feature Specification: Database Migration — SQLite to Production Database

**Feature Branch**: `005-database-migration`  
**Created**: 2026-03-23  
**Status**: Draft  
**Input**: User description: "I need to use a real database system, rather than sqlite. Let's plan out some options"

## Context

The application currently uses SQLite with the SpatiaLite extension as its sole database. While SQLite works well for local development and single-user scenarios, it has significant limitations for a production deployment:

- **No concurrent write support**: SQLite uses file-level locking, meaning only one write can occur at a time. The application already manages background sync tasks (Strava activity imports) that compete with user requests for write access.
- **No network access**: SQLite is an embedded database — it cannot be shared across multiple application instances or containers.
- **Limited scalability**: Cannot horizontally scale the backend behind a load balancer since each instance would have a separate database file.
- **Manual schema migrations**: The application currently uses hand-written `ALTER TABLE` statements executed at startup, which is fragile and error-prone.
- **Geospatial dependency**: The app relies heavily on SpatiaLite for spatial queries (street segments, neighborhood boundaries, coverage matching). Any replacement must provide equivalent geospatial capabilities.

### Database Options Evaluation

| Criteria | PostgreSQL + PostGIS | Azure SQL + Spatial Types | MySQL + Spatial Extensions |
|----------|---------------------|--------------------------|---------------------------|
| Geospatial maturity | Industry standard; direct SpatiaLite equivalent | Basic spatial types; limited function library | Partial; weaker spatial indexing |
| SQLAlchemy support | Excellent (first-class via GeoAlchemy2) | Good (via pyodbc); spatial support is manual | Good; spatial ORM support is limited |
| Azure managed option | Azure Database for PostgreSQL – Flexible Server | Azure SQL Database | Azure Database for MySQL |
| Migration effort from SpatiaLite | Low — same spatial function names and concepts | High — different function signatures, data types | Medium — partial function parity |
| Cost (Azure managed, General Purpose) | Comparable | Comparable | Comparable |
| Concurrent connections | Excellent | Excellent | Excellent |
| Community & ecosystem | Largest open-source DB community | Enterprise-focused | Large but declining for new projects |

**Recommendation**: PostgreSQL with PostGIS is the natural migration target. It shares spatial function semantics with SpatiaLite, has first-class SQLAlchemy/GeoAlchemy2 support, and is the industry standard for geospatial applications. The remainder of this spec assumes PostgreSQL + PostGIS as the sole database target (SQLite support will be removed).

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Application Runs on a Production-Grade Database (Priority: P1)

As an operator deploying the application, I need the system to connect to a production database that supports concurrent access so that multiple users and background sync processes can operate simultaneously without data corruption or locking errors.

**Why this priority**: This is the foundational change — nothing else matters if the application cannot connect to and operate against the new database. Every existing feature (activity sync, street coverage, route suggestions) must continue to work identically.

**Independent Test**: Deploy the application pointed at a PostgreSQL + PostGIS instance, run the existing test suite, and verify all CRUD operations, geospatial queries, and background syncs work correctly.

**Acceptance Scenarios**:

1. **Given** a PostgreSQL database with PostGIS enabled, **When** the application starts with that connection string, **Then** all required tables and spatial metadata are created automatically.
2. **Given** a running application connected to PostgreSQL, **When** a user triggers an activity sync while another user is browsing their coverage map, **Then** both operations complete without errors or blocking.
3. **Given** the existing SQLAlchemy models and queries, **When** executed against PostgreSQL + PostGIS, **Then** all geospatial operations (containment checks, distance calculations, intersection queries) return equivalent results to the SpatiaLite version.

---

### ~~User Story 2 — Existing Data Is Migrated Without Loss~~ (REMOVED)

*Removed per clarification: the application will start fresh on PostgreSQL. No data migration from SQLite is required.*

---

### User Story 2 — Schema Changes Are Managed Systematically (Priority: P2)

As a developer, I need database schema changes to be managed through a proper migration system so that schema updates are versioned, repeatable, and can be applied or rolled back safely.

**Why this priority**: The current approach of hand-written `ALTER TABLE` statements at startup is fragile. Moving to a production database is the right time to introduce proper schema migration tooling. This prevents data loss from failed migrations and enables team collaboration on schema changes.

**Independent Test**: Create a schema migration, apply it to a test database, verify the schema change, then roll it back and verify the original schema is restored.

**Acceptance Scenarios**:

1. **Given** a new schema change is needed, **When** a migration is created and applied, **Then** the database schema is updated correctly.
2. **Given** a migration has been applied, **When** a rollback is requested, **Then** the schema reverts to its prior state without data loss (where feasible).
3. **Given** an application deployment to a fresh environment, **When** all migrations run in sequence, **Then** the resulting schema is identical to an existing environment at the same migration version.

---

### User Story 3 — Local Development Remains Simple (Priority: P3)

As a developer, I need to easily run the application locally without requiring a full database server installation, so that onboarding and day-to-day development remain frictionless.

**Why this priority**: Developer experience matters. If the migration makes local development painful, it will slow down all future work. Providing a containerized database option or retaining SQLite for local dev keeps the barrier low.

**Independent Test**: Clone the repository, run the documented local setup steps, and verify the application starts and passes tests within a few minutes.

**Acceptance Scenarios**:

1. **Given** a developer cloning the repo for the first time, **When** they follow the setup instructions (including `docker compose up`), **Then** they have a working PostgreSQL + PostGIS database within 5 minutes.
2. **Given** a developer with Docker installed, **When** they run the documented startup command, **Then** the application connects to a local PostgreSQL container and is fully functional.

---

### User Story 4 — City & Neighborhood Bootstrap Works on PostgreSQL (Priority: P2)

As an operator deploying the application to a fresh PostgreSQL database, I need the automatic city/neighborhood bootstrap process to seed all reference data correctly so that users can immediately begin tracking street coverage.

**Why this priority**: The bootstrap is the first code path that runs against a fresh database. It creates cities, loads street segments with geometries, and populates neighborhood boundaries — all via spatial operations. If this fails on PostgreSQL, the application is non-functional. It also uses background threads and separate database sessions, exercising concurrent access from day one.

**Independent Test**: Start the application against an empty PostgreSQL + PostGIS database with `auto_load_cities_on_empty_db=true`, wait for bootstrap to complete, and verify all city, street, and neighborhood data is present and spatially queryable.

**Acceptance Scenarios**:

1. **Given** an empty PostgreSQL database with PostGIS enabled, **When** the application starts with `auto_load_cities_on_empty_db=true`, **Then** the city bootstrap runs to completion and cities, street segments, and neighborhoods are populated with valid geometries.
2. **Given** the bootstrap is running in a background thread, **When** a user makes API requests during bootstrap, **Then** the application returns appropriate status (e.g., "loading") without errors or database lock contention.
3. **Given** the bootstrap has completed, **When** a user queries their city's neighborhoods and street segments, **Then** all spatial queries (containment, intersection) return correct results.
4. **Given** the manual bootstrap endpoint is called via the admin API, **When** it triggers a city or neighborhood bootstrap, **Then** the bootstrap completes successfully against PostgreSQL.
5. **Given** a bootstrap fails partway through (e.g., network error fetching source data), **When** it is retried, **Then** it completes without leaving partial or duplicate data.

---

### Edge Cases

- What happens when the database connection is lost mid-request? The application should return a meaningful error and recover on the next request.
- What happens when a migration fails partway through? The migration tool must support transactional migrations that either fully apply or fully roll back.
- What happens when multiple application instances start simultaneously and attempt to run migrations? Only one instance should apply migrations; others should wait or detect the migration is already applied.
- How does the application handle the transition period during migration? SQLite code paths are removed; the application starts fresh on PostgreSQL with no backward compatibility needed.
- What if the bootstrap uses SQLite-specific SQL or SpatiaLite-specific function calls internally? All spatial function calls in the bootstrap and data-loading scripts must be verified and updated for PostGIS compatibility.
- What happens if the bootstrap thread's database session encounters a PostgreSQL-specific error (e.g., serialization failure)? The bootstrap must handle PostgreSQL error codes appropriately and retry or report clearly.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support connecting to PostgreSQL (with PostGIS) via a configurable connection string.
- **FR-002**: System MUST automatically create all required tables and spatial extensions when starting against an empty database.
- **FR-003**: System MUST support concurrent read and write operations from multiple users and background processes without data corruption.
- **FR-004**: System MUST preserve all existing geospatial query functionality (containment, intersection, distance, buffering) with equivalent results.
- **FR-005**: System MUST seed required reference data (cities, street segments, neighborhood boundaries) into a fresh PostgreSQL database via the existing city bootstrap process or a documented seed command.
- **FR-006**: System MUST use a versioned schema migration system for all schema changes going forward.
- **FR-007**: System MUST support migration rollback for schema changes (where feasible without destructive data loss).
- **FR-008**: System MUST NOT retain SQLite/SpatiaLite support; PostgreSQL + PostGIS is the sole supported database for all environments (production, CI, and local development).
- **FR-009**: System MUST provide a containerized database option for local development (e.g., via Docker Compose).
- **FR-010**: System MUST validate the database connection and spatial extension availability at startup, failing fast with a clear error message if requirements are not met.
- **FR-011**: System MUST handle database connection failures gracefully, returning appropriate error responses without crashing.
- **FR-012**: System MUST eliminate hand-written `ALTER TABLE` migration statements from application startup code once the migration system is in place.
- **FR-013**: System MUST authenticate to the production PostgreSQL database using Azure Managed Identity (passwordless), with no database credentials stored in application configuration.
- **FR-014**: System MUST use SQLAlchemy's built-in connection pool with configurable pool size and overflow limits; no external connection pooler (e.g., PgBouncer) is required.

### Key Entities

- **Database Connection**: Represents the configured connection to PostgreSQL/PostGIS, managed through environment configuration (connection string locally, Azure Managed Identity in production).
- **Schema Migration**: A versioned, ordered change to the database schema that can be applied forward or rolled back. Each migration has a unique identifier, a description, and up/down operations.
- **Spatial Extension**: PostGIS — the geospatial capability layer that provides geometry types, spatial functions, and spatial indexing.

## Clarifications

### Session 2026-03-23

- Q: How should the application authenticate to the production PostgreSQL database? → A: Azure Managed Identity (passwordless; no secrets stored)
- Q: Should local development use PostgreSQL via Docker or retain SQLite as fallback? → A: PostgreSQL via Docker only (drop SQLite support entirely)
- Q: When should the one-time SQLite-to-PostgreSQL data migration run? → A: No migration — start fresh in PostgreSQL; existing SQLite data is not carried over
- Q: Should the application use connection pooling, and if so, where? → A: SQLAlchemy built-in connection pool (no external components)

## Assumptions

- PostgreSQL + PostGIS is the sole database target. SQLite/SpatiaLite support will be removed entirely — no dual-database abstraction layer is needed.
- The existing SQLAlchemy ORM models and GeoAlchemy2 can abstract most database differences, minimizing application code changes.
- The Azure deployment will use Azure Database for PostgreSQL – Flexible Server as the managed database service.
- Production database authentication uses Azure Managed Identity (passwordless) — no database credentials are stored in configuration, environment variables, or Key Vault. Local development uses standard connection strings with local credentials.
- No data migration from the existing SQLite database is required. The application will start fresh — users will re-sync activities from Strava, and city/street data will be re-bootstrapped.
- Data volumes are moderate (thousands of activities, tens of thousands of street segments per city) — re-bootstrapping is fast enough to not require migration.
- Connection pooling is handled by SQLAlchemy's built-in pool (`pool_size` / `max_overflow` configuration). No external pooler (PgBouncer) is needed at current scale. This can be revisited if the application scales to many instances.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All existing automated tests pass against the new database with no test modifications required (beyond connection configuration).
- **SC-002**: The application supports at least 50 concurrent users performing read operations and 10 concurrent background sync processes without errors or timeouts.
- **SC-003**: Geospatial query results (coverage percentages, street matching, neighborhood lookups) produce correct results against PostgreSQL + PostGIS.
- **SC-004**: City bootstrap and street data seeding complete successfully on a fresh PostgreSQL database, with all geometries spatially indexed and queryable.
- **SC-005**: Bootstrap completes within the same time tolerance as the current SQLite-based bootstrap (no significant performance regression).
- **SC-006**: A new developer can set up a working local development environment (including database) in under 5 minutes following documentation.
- **SC-007**: Schema migrations can be applied to a fresh database and produce an identical schema to an existing environment in under 30 seconds.
- **SC-008**: Application startup detects a misconfigured or unreachable database and reports a clear error within 10 seconds rather than hanging or crashing silently.
