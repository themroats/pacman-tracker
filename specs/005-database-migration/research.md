# Research: Database Migration — SQLite to PostgreSQL

**Feature**: 005-database-migration  
**Date**: 2026-03-23

## R1: SpatiaLite → PostGIS Function Mapping

### Decision
All SpatiaLite-specific SQL must be rewritten to use PostGIS equivalents or standard GeoAlchemy2 ORM expressions.

### Rationale
The codebase uses three categories of spatial operations:
1. **GeoAlchemy2 ORM calls** (e.g., `gfunc.ST_Intersects`, `gfunc.ST_Within`) — these are database-agnostic and work identically on PostGIS. **No changes needed.**
2. **SpatiaLite R-tree virtual table queries** (e.g., `SELECT ROWID FROM SpatialIndex WHERE ...`) — these are SQLite-specific. PostGIS uses GiST indexes automatically through the query planner. **Must rewrite to standard `ST_Intersects` / `ST_Within` with `&&` bbox operator.**
3. **SpatiaLite initialization calls** (`InitSpatialMetaData(1)`, `enable_load_extension`, `PRAGMA foreign_keys`) — replaced by `CREATE EXTENSION IF NOT EXISTS postgis`.

### Function mapping

| SpatiaLite | PostGIS Equivalent | Notes |
|---|---|---|
| `InitSpatialMetaData(1)` | `CREATE EXTENSION IF NOT EXISTS postgis` | One-time per database |
| `BuildMbr(minx,miny,maxx,maxy,srid)` | `ST_MakeEnvelope(minx,miny,maxx,maxy,srid)` | Or use `&&` operator with `ST_MakeEnvelope` |
| `SpatialIndex` virtual table | GiST index (automatic via GeoAlchemy2) | No explicit R-tree queries needed |
| `GeomFromText(wkt, srid)` | `ST_GeomFromText(wkt, srid)` | Same function name in PostGIS |
| `ST_Within(a, b)` | `ST_Within(a, b)` | Identical |
| `ST_Centroid(geom)` | `ST_Centroid(geom)` | Identical |
| `ST_Intersects(a, b)` | `ST_Intersects(a, b)` | Identical |
| `PRAGMA foreign_keys = ON` | (default behavior) | PostgreSQL enforces FKs by default |
| `ROWID` | Primary key column | No implicit ROWID in PostgreSQL |

### Alternatives considered
- **Database abstraction layer**: Wrapping all spatial calls in a compatibility layer. Rejected — adds unnecessary complexity since we're dropping SQLite entirely.
- **Raw SQL for PostGIS R-tree**: Writing explicit GiST index hints. Rejected — PostGIS query planner handles this automatically for `ST_*` functions on indexed columns.

## R2: R-tree Spatial Index Migration Strategy

### Decision
Replace all explicit `SpatialIndex` virtual table queries with standard GeoAlchemy2 filter expressions using `ST_Intersects` with `ST_MakeEnvelope`. PostGIS GiST indexes will be used transparently by the query planner.

### Rationale
SpatiaLite requires explicit R-tree index queries via a virtual table because its query planner cannot automatically use spatial indexes. PostGIS has a mature query planner that automatically uses GiST indexes when `ST_*` functions are applied to indexed geometry columns. The `&&` operator (bounding box overlap) is the GiST index entry point.

### Affected locations
1. `backend/app/services/coverage.py` — Street matching pre-filter via `SpatialIndex`
2. `backend/app/scripts/load_neighborhoods.py` — Neighborhood assignment via `SpatialIndex`
3. `backend/app/services/routing.py` — Candidate street filtering (if present)

### Migration pattern
```python
# BEFORE (SpatiaLite R-tree)
text("SELECT ROWID FROM SpatialIndex WHERE f_table_name=:tbl AND search_frame=BuildMbr(:minx,:miny,:maxx,:maxy,4326)")

# AFTER (PostGIS with GeoAlchemy2)
from geoalchemy2 import functions as gfunc
query.filter(
    StreetSegment.geometry.intersects(
        gfunc.ST_MakeEnvelope(minx, miny, maxx, maxy, 4326)
    )
)
```

### Alternatives considered
- **Keep raw SQL with PostGIS syntax**: Use `ST_MakeEnvelope` in raw text queries. Rejected — ORM expressions are safer, type-checked, and maintain the existing pattern.

## R3: Azure Managed Identity for PostgreSQL Authentication

### Decision
Use `azure-identity` Python package with `DefaultAzureCredential` to obtain access tokens for Azure Database for PostgreSQL Flexible Server. Tokens are passed via SQLAlchemy's `creator` callback or connection event.

### Rationale
Azure Managed Identity eliminates credentials from configuration. The `DefaultAzureCredential` class automatically works in both development (Azure CLI login) and production (system-assigned managed identity) environments.

### Implementation pattern
```python
from azure.identity import DefaultAzureCredential

def _get_pg_connection_with_token():
    credential = DefaultAzureCredential()
    token = credential.get_token("https://ossrdbms-aad.database.windows.net/.default")
    # Use token.token as the password in the connection string
    conn = psycopg2.connect(
        host="server.postgres.database.azure.com",
        dbname="pacman",
        user="managed-identity-name",
        password=token.token,
        sslmode="require",
    )
    return conn
```

### Dependencies required
- `azure-identity` — Azure credential management
- `psycopg2-binary` or `psycopg[binary]` — PostgreSQL driver (replaces sqlite3)

### Alternatives considered
- **Connection string with password in Key Vault**: Requires Key Vault setup, secret rotation. Rejected — Managed Identity is simpler and more secure.
- **Connection string in environment variable**: Credentials exposed in config. Rejected — violates security requirements.

## R4: Alembic for Schema Migrations

### Decision
Use Alembic as the schema migration tool. Generate an initial migration from the current SQLAlchemy models to establish a baseline, then manage all future changes through Alembic migrations.

### Rationale
Alembic is the de facto migration tool for SQLAlchemy. It integrates natively with the existing ORM models, supports auto-generation of migrations from model changes, and provides transactional DDL on PostgreSQL (entire migration runs in a transaction — it either fully applies or fully rolls back).

### Key features
- **Auto-generate**: `alembic revision --autogenerate -m "description"` compares models to DB schema
- **Transactional DDL**: PostgreSQL wraps migrations in a transaction by default
- **Migration locking**: `alembic upgrade head` acquires an advisory lock preventing concurrent migrations
- **PostGIS support**: GeoAlchemy2 provides Alembic dialect extensions for spatial columns

### Setup
```
backend/
├── alembic.ini           # Alembic configuration
├── alembic/
│   ├── env.py            # References app.database.Base.metadata
│   ├── script.py.mako    # Migration template
│   └── versions/
│       └── 001_initial_schema.py  # Baseline migration
```

### Alternatives considered
- **Django-style migrations**: Not applicable — project uses FastAPI + SQLAlchemy.
- **Flyway / Liquibase**: Java-based tools. Rejected — unnecessary complexity for a Python project.
- **Manual SQL scripts**: Current approach. Rejected — fragile, no version tracking, no rollback.

## R5: Test Infrastructure Migration

### Decision
Replace in-memory SpatiaLite test database with PostgreSQL via `testcontainers-python`. Each test session spins up a disposable PostgreSQL + PostGIS Docker container.

### Rationale
Since SQLite is being dropped entirely, tests must run against PostgreSQL. `testcontainers-python` provides ephemeral containers that are created per-session and destroyed after tests complete. This ensures dev/prod parity in the test suite.

### Implementation
```python
# conftest.py
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("postgis/postgis:16-3.4") as pg:
        yield pg

@pytest.fixture(scope="session")
def engine(pg_container):
    url = pg_container.get_connection_url()
    engine = create_engine(url)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    return engine
```

### Dependencies required
- `testcontainers[postgres]` — Disposable Docker containers for tests
- Docker must be running on CI and developer machines

### Alternatives considered
- **Shared test PostgreSQL instance**: Requires manual setup, port conflicts. Rejected — not reproducible.
- **SQLite for tests only**: Tests wouldn't catch postgres-specific issues. Rejected — contradicts "drop SQLite" decision.
- **GitHub Actions PostgreSQL service**: Works for CI but not local development. Insufficient alone.

## R6: Docker Compose PostgreSQL Service

### Decision
Add a `postgis/postgis:16-3.4` container to the existing `docker-compose.yml` for local development. This replaces the file-based SQLite database.

### Rationale
Developers need a one-command setup (`docker compose up`) to get a working PostgreSQL + PostGIS instance. The existing docker-compose already manages the OSRM routing container; adding a database container follows the same pattern.

### Container configuration
```yaml
services:
  db:
    image: postgis/postgis:16-3.4
    environment:
      POSTGRES_DB: pacman
      POSTGRES_USER: pacman
      POSTGRES_PASSWORD: pacman_dev
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pacman -d pacman"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
```

### Alternatives considered
- **Manual PostgreSQL installation**: Too much friction for onboarding. Rejected.
- **Embedded PostgreSQL (embedded-postgres)**: Python wrapper around PG binaries. Rejected — fragile, not production-representative.
