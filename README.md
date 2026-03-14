# Pac-Man Tracker

A street coverage tracker that connects to your Strava account and visualizes which streets you've run (or walked/cycled) — like Pac-Man eating dots on a map.

## Overview

Pac-Man Tracker imports your Strava activities, matches the GPS traces against OpenStreetMap street data, and builds a coverage map showing which streets you've traveled and which ones are still waiting. It also suggests routes through uncovered streets so you can efficiently fill in the gaps.

### Key Features

- **Strava Integration** — OAuth2 login, automatic activity sync, webhook-based real-time updates
- **GPS-to-Street Matching** — Buffers GPS traces by 15m and computes intersection ratios against street segments
- **Coverage Dashboard** — City → neighborhood → street drill-down with percentage progress
- **Interactive Map** — Color-coded street overlay (traveled vs untraveled) with activity layers
- **Route Suggestions** — Uses OSRM to generate walking routes through uncovered streets
- **Progress Timeline** — Daily snapshots with milestone detection (25%, 50%, 75%, 100%)

## Architecture

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│   Frontend   │──────▶│   Backend    │──────▶│   Strava     │
│  React SPA   │  REST │  FastAPI     │ OAuth │   API        │
│  :5173       │◀──────│  :8000       │◀──────│              │
└──────────────┘       └──────┬───────┘       └──────────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
              ┌─────▼─────┐     ┌───────▼──────┐
              │  SQLite/   │     │  OSRM        │
              │ SpatiaLite │     │  :5000       │
              │  (DB)      │     │  (routing)   │
              └────────────┘     └──────────────┘
```

| Component | Tech Stack |
|-----------|-----------|
| **Frontend** | React 18, TypeScript, Vite, react-leaflet, Zustand |
| **Backend** | Python 3.12+, FastAPI, SQLAlchemy, GeoAlchemy2 |
| **Database** | SQLite + SpatiaLite (local dev) |
| **Routing** | OSRM with foot profile (via Docker) |
| **Geospatial** | Shapely, GeoPandas, OSMnx, pyproj |

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- Docker (for OSRM routing server)
- A [Strava API Application](https://www.strava.com/settings/api)

### 1. Clone and configure

```bash
git clone <repo-url> pacman-tracker
cd pacman-tracker

# Backend env
cp backend/.env.example backend/.env
# Edit backend/.env with your Strava credentials and a SECRET_KEY
```

### 2. Backend setup

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt

# Initialize the database
python -m app.scripts.init_db

# Load street data for supported cities
python -m app.scripts.load_cities

# Start the API server
uvicorn app.main:app --reload --port 8000
```

### 2a. Local Docker backend helper

If you want to clear out the old local backend container, rebuild the image, and run it again with the existing env file and data volume, use:

```powershell
.\infra\run-local-backend.ps1 -Detach
```

Useful options:

```powershell
.\infra\run-local-backend.ps1 -RemoveImage -PruneDangling -Detach
```

When the backend runs in Docker and OSRM runs on the host machine, set `OSRM_URL=http://host.docker.internal:5000` in `backend/.env`. If you run the backend directly on the host, `http://localhost:5000` is still the right value.

### 3. Frontend setup

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### 4. OSRM routing server (optional — needed for route suggestions)

```bash
# From project root
docker compose --profile prepare up osrm-prepare   # One-time: downloads + processes OSM data
docker compose up osrm                              # Start routing server on :5000
```

## Project Structure

```
pacman-tracker/
├── README.md                 ← You are here
├── docker-compose.yml        ← OSRM routing server
├── infra/
│   ├── deploy-prod.ps1       ← Production deployment helper
│   └── run-local-backend.ps1 ← Local Docker cleanup + rebuild + run helper
├── backend/
│   ├── README.md             ← Backend-specific docs
│   ├── .env.example          ← Environment variable template
│   ├── pyproject.toml        ← Project metadata + tool config
│   ├── requirements.txt      ← Python dependencies
│   ├── app/
│   │   ├── main.py           ← FastAPI app factory + lifespan
│   │   ├── config.py         ← Pydantic settings (env vars)
│   │   ├── database.py       ← SQLAlchemy engine + session management
│   │   ├── api/              ← Route handlers (8 routers)
│   │   ├── models/           ← SQLAlchemy ORM models (7 models)
│   │   ├── schemas/          ← Pydantic request/response schemas
│   │   ├── services/         ← Business logic layer (7 services)
│   │   └── scripts/          ← DB init + city data loading
│   └── tests/                ← pytest: contract, unit, integration
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── App.tsx           ← Router + layout
│   │   ├── api/              ← HTTP client
│   │   ├── components/       ← React components
│   │   ├── hooks/            ← Custom React hooks
│   │   ├── pages/            ← Page-level components
│   │   ├── store/            ← Zustand state management
│   │   ├── types/            ← TypeScript type definitions
│   │   └── utils/            ← Helper functions
│   └── tests/                ← Vitest component tests
└── specs/                    ← Feature specifications
```

## Running Tests

```bash
# Backend
cd backend
pytest                    # Run all tests
pytest --cov=app          # With coverage report
pytest tests/unit/        # Unit tests only

# Frontend
cd frontend
npm test                  # Run Vitest in watch mode
npm run test:coverage     # With coverage
```

## Supported Cities

The street data loader includes five launch cities:

| City | State | Projected CRS |
|------|-------|---------------|
| Seattle | Washington | EPSG:2926 |
| Pittsburgh | Pennsylvania | EPSG:2272 |
| Chicago | Illinois | EPSG:3435 |
| New York | New York | EPSG:2263 |
| San Francisco | California | EPSG:2227 |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `STRAVA_CLIENT_ID` | Yes | — | From Strava API settings |
| `STRAVA_CLIENT_SECRET` | Yes | — | From Strava API settings |
| `STRAVA_REDIRECT_URI` | No | `http://localhost:8000/api/v1/auth/strava/callback` | OAuth redirect URL |
| `STRAVA_WEBHOOK_VERIFY_TOKEN` | No | `pacman-tracker-verify` | Webhook subscription token |
| `SECRET_KEY` | Yes | — | 32+ char string for Fernet encryption |
| `DATABASE_URL` | No | `sqlite:///./data/pacman.db` | Database connection string |
| `OSRM_URL` | No | `http://localhost:5000` | OSRM routing server |
| `CORS_ORIGINS` | No | `http://localhost:5173` | Comma-separated allowed origins |

## License

MIT
