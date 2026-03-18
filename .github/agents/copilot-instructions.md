# pacman-tracker Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-02-28

## Active Technologies
- Python 3.12+ (backend), TypeScript 5.6 (frontend) + FastAPI, SQLAlchemy 2.0, GeoAlchemy2, Shapely, React 18.3, Zustand, Leaflet/React-Leaflet (002-app-stability-hardening)
- SQLite + SpatiaLite (`./data/pacman.db`) (002-app-stability-hardening)

- Python 3.12+ (backend), TypeScript 5.x (frontend) + FastAPI, Uvicorn, Shapely, GeoPandas, OSMnx, react-leaflet, OSRM (001-strava-street-mapper)

## Project Structure

```text
backend/
frontend/
tests/
```

## Commands

cd src; pytest; ruff check .

## Code Style

Python 3.12+ (backend), TypeScript 5.x (frontend): Follow standard conventions

## Recent Changes
- 002-app-stability-hardening: Added Python 3.12+ (backend), TypeScript 5.6 (frontend) + FastAPI, SQLAlchemy 2.0, GeoAlchemy2, Shapely, React 18.3, Zustand, Leaflet/React-Leaflet

- 001-strava-street-mapper: Added Python 3.12+ (backend), TypeScript 5.x (frontend) + FastAPI, Uvicorn, Shapely, GeoPandas, OSMnx, react-leaflet, OSRM

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
