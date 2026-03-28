# Quickstart: Database Migration — Local Development Setup

**Feature**: 005-database-migration  
**Date**: 2026-03-23

## Prerequisites

- Docker Desktop installed and running
- Python 3.12+
- Git

## Setup Steps

### 1. Start the database

```bash
docker compose up db -d
```

This starts a PostgreSQL 16 + PostGIS 3.4 container on port 5432 with:
- Database: `pacman`
- User: `pacman`
- Password: `pacman_dev`

Wait for the health check to pass:
```bash
docker compose ps  # Should show "healthy"
```

### 2. Configure the backend

Create or update `backend/.env`:

```env
DATABASE_URL=postgresql://pacman:pacman_dev@localhost:5432/pacman
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
```

### 3. Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 4. Run database migrations

```bash
cd backend
alembic upgrade head
```

This creates all tables and enables the PostGIS extension.

### 5. Start the application

```bash
uvicorn app.main:app --reload
```

On first startup with `auto_load_cities_on_empty_db=true` (the default), the city bootstrap will automatically download and populate street data from OpenStreetMap.

### 6. Run tests

```bash
cd backend
pytest
```

Tests use `testcontainers-python` to spin up an ephemeral PostgreSQL + PostGIS Docker container. Docker must be running.

## Full stack (backend + OSRM + database)

```bash
docker compose up -d          # Starts db + OSRM routing services
cd backend
alembic upgrade head          # Apply migrations
uvicorn app.main:app --reload # Start backend
```

In a separate terminal:
```bash
cd frontend
npm install
npm run dev
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `connection refused` on port 5432 | Run `docker compose up db -d` and wait for health check |
| `postgis extension not found` | Ensure you're using the `postgis/postgis:16-3.4` image, not plain `postgres` |
| Tests fail with "Docker not running" | Start Docker Desktop; testcontainers requires a running Docker daemon |
| `alembic upgrade head` fails | Check `DATABASE_URL` in `.env` matches the running container |

## Resetting the database

```bash
docker compose down -v  # Removes the pgdata volume
docker compose up db -d # Fresh database
alembic upgrade head    # Re-apply migrations
```
