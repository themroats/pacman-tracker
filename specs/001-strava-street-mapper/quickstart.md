# Quickstart: Strava Street Mapper

**Feature**: 001-strava-street-mapper  
**Date**: 2026-02-28

## Prerequisites

- Python 3.12+
- Node.js 18+ / npm 9+
- Docker (for OSRM routing engine)
- A Strava API application (for OAuth credentials)

## 1. Clone & Setup

```bash
git clone <repo-url>
cd pacman-tracker
git checkout 001-strava-street-mapper
```

## 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Strava API credentials:
#   STRAVA_CLIENT_ID=<your-client-id>
#   STRAVA_CLIENT_SECRET=<your-client-secret>
#   STRAVA_REDIRECT_URI=http://localhost:8000/api/v1/auth/strava/callback
#   SECRET_KEY=<random-secret-for-token-encryption>
#   DATABASE_URL=sqlite:///./data/pacman.db

# Initialize database + load city data
python -m app.scripts.init_db
python -m app.scripts.load_cities  # Downloads OSM street networks for 5 launch cities

# Start the API server
uvicorn app.main:app --reload --port 8000
```

## 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env
# Edit .env:
#   VITE_API_URL=http://localhost:8000/api/v1

# Start dev server
npm run dev
# → Opens at http://localhost:5173
```

## 4. OSRM Setup (for route suggestions)

```bash
# Download city OSM extract (example: Seattle)
wget https://download.geofabrik.de/north-america/us/washington-latest.osm.pbf

# Prepare OSRM data
docker run -t -v "${PWD}/osrm-data:/data" osrm/osrm-backend osrm-extract -p /opt/foot.lua /data/washington-latest.osm.pbf
docker run -t -v "${PWD}/osrm-data:/data" osrm/osrm-backend osrm-partition /data/washington-latest.osrm
docker run -t -v "${PWD}/osrm-data:/data" osrm/osrm-backend osrm-customize /data/washington-latest.osrm

# Start OSRM server
docker run -t -p 5000:5000 -v "${PWD}/osrm-data:/data" osrm/osrm-backend osrm-routed --algorithm mld /data/washington-latest.osrm
```

## 5. Verify Setup

1. Open `http://localhost:5173` in your browser
2. Click "Connect with Strava" → authorize the app
3. Activities should begin importing (check sync status)
4. Select a city/neighborhood to see street coverage

## Key Backend Commands

```bash
# Run tests
pytest

# Lint & format
ruff check . && ruff format .

# Load/refresh street data for a specific city
python -m app.scripts.load_cities --city "Seattle"
```

## Key Frontend Commands

```bash
# Run tests
npm test

# Lint & format
npm run lint && npm run format

# Build for production
npm run build
```

## Project Structure

```
pacman-tracker/
├── backend/
│   ├── app/                # FastAPI application
│   │   ├── api/            # Route handlers
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   └── services/       # Business logic
│   └── tests/              # pytest tests
├── frontend/
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── pages/          # Page-level components
│   │   ├── api/            # API client
│   │   └── hooks/          # Custom hooks
│   └── tests/              # Vitest tests
└── specs/                  # Feature specifications
```

## Environment Variables

### Backend (.env)

| Variable | Required | Description |
|----------|----------|-------------|
| STRAVA_CLIENT_ID | yes | Your Strava API application ID |
| STRAVA_CLIENT_SECRET | yes | Your Strava API application secret |
| STRAVA_REDIRECT_URI | yes | OAuth callback URL |
| SECRET_KEY | yes | Secret for encrypting tokens |
| DATABASE_URL | yes | SQLite/PostgreSQL connection string |
| OSRM_BASE_URL | no | OSRM server URL (default: http://localhost:5000) |

### Frontend (.env)

| Variable | Required | Description |
|----------|----------|-------------|
| VITE_API_URL | yes | Backend API base URL |
