# Pac-Man Tracker — Backend

FastAPI backend for the Pac-Man Tracker street coverage application.

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Framework | FastAPI 0.109+ | Async REST API with automatic OpenAPI docs |
| ORM | SQLAlchemy 2.0+ | Database models + session management |
| Geospatial | GeoAlchemy2, Shapely, GeoPandas | Geometry columns, GPS math, spatial analysis |
| Auth | Strava OAuth2, Fernet encryption | User login via Strava, encrypted token storage |
| HTTP Client | httpx | Async calls to Strava API |
| Routing | OSRM (external) | Walking route suggestions |
| Config | Pydantic Settings | Type-safe environment variable loading |
| Testing | pytest, pytest-asyncio | Unit, contract, and integration tests |
| Linting | Ruff | Fast Python linter + formatter |

## Getting Started

### 1. Environment setup

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in:

- `STRAVA_CLIENT_ID` / `STRAVA_CLIENT_SECRET` — from [Strava API settings](https://www.strava.com/settings/api)
- `SECRET_KEY` — generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`

### 3. Initialize the database

```bash
python -m app.scripts.init_db       # Create tables + spatial indexes
python -m app.scripts.load_cities   # Download street data for launch cities (~5-10 min)
```

### 4. Start the server

```bash
uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000/api/v1
- OpenAPI docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Architecture

```
app/
├── main.py          ← App factory, CORS, lifespan events, error handling
├── config.py        ← Pydantic Settings (loads .env)
├── database.py      ← SQLAlchemy engine, sessions, SpatiaLite extension
│
├── models/          ← ORM models (7 tables)
│   ├── user.py              User (Strava athlete, encrypted tokens)
│   ├── activity.py          Activity (Strava activity + GPS data)
│   ├── city.py              City (boundary, metadata)
│   ├── neighborhood.py      Neighborhood (within city)
│   ├── street.py            StreetSegment (OSM road geometry)
│   ├── coverage.py          UserStreetCoverage + CoverageSnapshot
│   └── route.py             RouteSuggestion + RouteSuggestionSegment
│
├── schemas/         ← Pydantic request/response models
│   ├── user.py              Auth responses
│   ├── activity.py          Activity list/detail/GeoJSON
│   ├── coverage.py          Coverage stats + GeoJSON
│   ├── progress.py          Timeline + milestones
│   └── route.py             Route suggestion request/response
│
├── services/        ← Business logic layer
│   ├── strava.py            Strava API client (OAuth, activities, streams)
│   ├── importer.py          Two-phase activity import pipeline
│   ├── coverage.py          GPS-to-street matching + ratio computation
│   ├── routing.py           OSRM client + route suggestion engine
│   ├── progress.py          Daily snapshots + milestone detection
│   ├── crypto.py            Fernet token encryption/decryption
│   └── webhook.py           Strava webhook event handler
│
├── api/             ← Route handlers (all under /api/v1)
│   ├── auth.py              OAuth flow (login, callback, logout)
│   ├── sync.py              Activity sync (status, trigger)
│   ├── activities.py        Activity CRUD + GeoJSON
│   ├── cities.py            City/neighborhood listing
│   ├── coverage.py          Coverage stats + street GeoJSON
│   ├── progress.py          Timeline + overall stats
│   ├── routes.py            Route suggestions + history
│   └── webhook.py           Strava webhook subscription
│
└── scripts/         ← CLI utilities
    ├── init_db.py           Create tables + spatial indexes
    ├── load_cities.py       Download OSM street data via OSMnx
    └── refresh_streets.py   Re-download streets (placeholder)
```

## API Reference

All endpoints are prefixed with `/api/v1`.

### Auth

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/auth/strava` | Redirect to Strava OAuth login |
| `GET` | `/auth/strava/callback` | Handle OAuth callback, create/update user |
| `POST` | `/auth/logout` | End user session |

### Sync

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/sync/status` | Get current sync status for user |
| `POST` | `/sync/trigger` | Trigger full activity import (Phase A + B) |

### Activities

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/activities` | List activities with filters + pagination |
| `GET` | `/activities/{id}` | Activity detail with GPS trace |
| `GET` | `/activities/geojson` | All activities as GeoJSON FeatureCollection |
| `GET` | `/activities/{id}/geojson` | Single activity as GeoJSON Feature |

**Query params for list:** `sport_type`, `start_date`, `end_date`, `has_gps`, `page`, `per_page`

### Cities

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/cities` | List all supported cities |
| `GET` | `/cities/{id}/neighborhoods` | Neighborhoods in a city with coverage % |
| `GET` | `/cities/{id}/neighborhoods/{nid}/boundary` | Neighborhood boundary GeoJSON |

### Admin

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/admin/bootstrap/cities` | Get manual city bootstrap status (requires `X-Admin-Token`) |
| `POST` | `/admin/bootstrap/cities` | Start manual city bootstrap (requires `X-Admin-Token`) |

Set `MANUAL_BOOTSTRAP_TOKEN` in the backend environment to enable these endpoints.

### Coverage

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/coverage/city/{id}` | City coverage summary + neighborhoods |
| `GET` | `/coverage/neighborhood/{id}` | Neighborhood detail + boundary |
| `GET` | `/coverage/neighborhood/{id}/streets` | Street GeoJSON for neighborhood |
| `GET` | `/coverage/city/{id}/streets` | Street GeoJSON for city (with bbox filter) |

**Query params for streets:** `status` (traveled/untraveled), `neighborhood_id`, `bbox`

### Progress

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/progress/city/{id}` | City timeline with daily snapshots |
| `GET` | `/progress/stats` | Overall stats (activities, distance, cities) |

### Routes

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/routes/suggest` | Generate a route through uncovered streets |
| `GET` | `/routes/history` | List previously generated routes |

**Request body for suggest:**

```json
{
  "neighborhood_id": 1,
  "target_distance_meters": 5000,
  "start_lat": 47.6062,
  "start_lng": -122.3321
}
```

### Webhooks

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/webhook/strava` | Strava subscription verification |
| `POST` | `/webhook/strava` | Handle Strava push events |

## Data Model

```
User 1──* Activity
City 1──* Neighborhood 1──* StreetSegment
User + StreetSegment *──1 UserStreetCoverage
User + City + Date  *──1 CoverageSnapshot
User 1──* RouteSuggestion 1──* RouteSuggestionSegment
```

### Key relationships

- **User → Activity**: One user has many Strava activities
- **City → Neighborhood → StreetSegment**: Geographic hierarchy
- **UserStreetCoverage**: Junction table — one row per user + street, tracks `coverage_ratio` and `is_traveled` (≥80%)
- **CoverageSnapshot**: Daily progress snapshot per user + city, with milestone flags

### Coverage algorithm

1. Buffer the GPS trace by 15m to account for GPS drift
2. Intersect the buffer with each street segment geometry
3. Compute `coverage_ratio = intersection_length / street_length` (clamped 0–1)
4. Mark `is_traveled = True` if ratio ≥ 0.80
5. Mark activity as `is_on_street = True` if overall ratio ≥ 0.20
6. Persist the max ratio across all activities (coverage only goes up)

## Testing

```bash
# Run all tests
pytest

# Verbose with coverage
pytest -v --cov=app --cov-report=term-missing

# Specific test layer
pytest tests/unit/
pytest tests/integration/
pytest tests/contract/

# Specific test file
pytest tests/unit/test_coverage.py -v
```

### Test structure

| Layer | Directory | What it tests | Mocking strategy |
|-------|-----------|--------------|------------------|
| **Contract** | `tests/contract/` | Strava API response parsing | Mocked HTTP, real service logic |
| **Unit** | `tests/unit/` | Business logic (coverage math, routing, progress) | Mocked DB + external services |
| **Integration** | `tests/integration/` | Full API endpoints via TestClient | In-memory SpatiaLite DB |

### Current status

- **43 tests passing**, 13 skipped (SpatiaLite not available on Windows)
- Integration tests require SpatiaLite extension — install `mod_spatialite` or run on Linux/macOS

## Database

### Local development (SQLite + SpatiaLite)

Default `DATABASE_URL=sqlite:///./data/pacman.db`. SpatiaLite adds geospatial functions to SQLite.

**Installing SpatiaLite:**

- **Ubuntu/Debian**: `sudo apt install libsqlite3-mod-spatialite`
- **macOS (Homebrew)**: `brew install libspatialite`
- **Windows**: Download from [Gaia-SINS](http://www.gaia-gis.it/gaia-sins/) and add to PATH

### Schema initialization

```bash
python -m app.scripts.init_db
```

Creates all tables and spatial indexes (SpatiaLite R-tree or PostGIS GiST depending on backend).

### Street data loading

```bash
python -m app.scripts.load_cities
```

Downloads street networks from OpenStreetMap via OSMnx for 5 launch cities. Takes ~5-10 minutes depending on network speed.

## Development

### Code style

Ruff handles both linting and formatting:

```bash
ruff check .          # Lint
ruff check --fix .    # Auto-fix
ruff format .         # Format
```

Configuration is in `pyproject.toml` under `[tool.ruff]`.

### Adding a new city

1. Add the city to the `CITIES` list in `app/scripts/load_cities.py`
2. Include `name`, `state`, `country`, `center (lat, lng)`, `network_type`, and `projected_crs`
3. Run `python -m app.scripts.load_cities` (existing cities are skipped)

### Adding a new API endpoint

1. Create or edit a router file in `app/api/`
2. Add schemas to `app/schemas/` if needed
3. Put business logic in `app/services/`, not in the route handler
4. Register the router in `app/main.py` → `create_app()`
5. Add tests in `tests/unit/` (logic) and `tests/integration/` (HTTP)

## Known Issues

- **Sync error rollback** (T101): When `POST /sync/trigger` fails mid-import, the error status is rolled back by the session cleanup. Error state is not persisted.
- **Duplicate coverage calc** (T102): `cities.py` has copy-pasted coverage calculation in two endpoints — should use a shared helper.
- **Fat route endpoint** (T103): `POST /routes/suggest` contains ~140 lines mixing HTTP, DB, and OSRM logic — should be extracted to the routing service.
