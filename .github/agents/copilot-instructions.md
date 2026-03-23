# pacman-tracker Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-02-28

## Active Technologies
- Python 3.12+ (backend), TypeScript 5.6 (frontend) + FastAPI, SQLAlchemy 2.0, GeoAlchemy2, Shapely, React 18.3, Zustand, Leaflet/React-Leaflet (002-app-stability-hardening)
- SQLite + SpatiaLite (`./data/pacman.db`) (002-app-stability-hardening)
- PowerShell (Azure CLI commands), Shell scripts (ACI entrypoints) + Azure CLI, `osrm/osrm-backend:latest` container image (003-deploy-routing-service)
- Azure File Share (Standard LRS, ~2.5 GB OSRM data) (003-deploy-routing-service)

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
- 003-deploy-routing-service: Added PowerShell (Azure CLI commands), Shell scripts (ACI entrypoints) + Azure CLI, `osrm/osrm-backend:latest` container image
- 002-app-stability-hardening: Added Python 3.12+ (backend), TypeScript 5.6 (frontend) + FastAPI, SQLAlchemy 2.0, GeoAlchemy2, Shapely, React 18.3, Zustand, Leaflet/React-Leaflet

- 001-strava-street-mapper: Added Python 3.12+ (backend), TypeScript 5.x (frontend) + FastAPI, Uvicorn, Shapely, GeoPandas, OSMnx, react-leaflet, OSRM

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
