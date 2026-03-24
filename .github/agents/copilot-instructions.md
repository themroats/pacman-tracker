# pacman-tracker Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-02-28

## Active Technologies
- Python 3.12+ (backend), TypeScript 5.6 (frontend) + FastAPI, SQLAlchemy 2.0, GeoAlchemy2, Shapely, React 18.3, Zustand, Leaflet/React-Leaflet (002-app-stability-hardening)
- SQLite + SpatiaLite (`./data/pacman.db`) (002-app-stability-hardening)
- PowerShell (Azure CLI commands), Shell scripts (ACI entrypoints) + Azure CLI, `osrm/osrm-backend:latest` container image (003-deploy-routing-service)
- Azure File Share (Standard LRS, ~2.5 GB OSRM data) (003-deploy-routing-service)
- TypeScript ~5.6, React 18.3, Vite 6.0 + react-router-dom 6.22, zustand 4.5, leaflet 1.9.4, react-leaflet 4.2.1 (004-mobile-responsive-ui)
- N/A (frontend-only changes, no data model changes) (004-mobile-responsive-ui)

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
- 004-mobile-responsive-ui: Added TypeScript ~5.6, React 18.3, Vite 6.0 + react-router-dom 6.22, zustand 4.5, leaflet 1.9.4, react-leaflet 4.2.1
- 003-deploy-routing-service: Added PowerShell (Azure CLI commands), Shell scripts (ACI entrypoints) + Azure CLI, `osrm/osrm-backend:latest` container image
- 002-app-stability-hardening: Added Python 3.12+ (backend), TypeScript 5.6 (frontend) + FastAPI, SQLAlchemy 2.0, GeoAlchemy2, Shapely, React 18.3, Zustand, Leaflet/React-Leaflet


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
