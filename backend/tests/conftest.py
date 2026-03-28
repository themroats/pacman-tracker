"""
Pytest configuration and shared test fixtures for the Strava Street Mapper backend.

Provides:
- PostgreSQL + PostGIS test database (uses the Docker Compose db service)
- Sample geometry factories for streets, GPS traces, neighborhoods, cities
- User and activity factory helpers
"""

import datetime
import os
from collections.abc import Generator
from typing import Any

import pytest
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

# Test database URL: uses a separate database on the same Docker Compose PG instance
_TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://pacman:pacman_dev@localhost:5432/pacman_test",
)

_pg_engine = None


def pytest_configure(config):
    """Create a dedicated test database on the Docker Compose PostgreSQL instance."""
    global _pg_engine

    # Disable city bootstrap in tests — prevents OSM downloads
    os.environ["AUTO_LOAD_CITIES_ON_EMPTY_DB"] = "false"

    # Connect to the default 'pacman' database to create the test database
    admin_url = _TEST_DB_URL.rsplit("/", 1)[0] + "/pacman"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        # Create test database if it doesn't exist
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = 'pacman_test'")
        ).scalar()
        if not exists:
            conn.execute(text("CREATE DATABASE pacman_test"))
    admin_engine.dispose()

    # Connect to the test database and enable PostGIS
    _pg_engine = create_engine(_TEST_DB_URL, echo=False)
    with _pg_engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.commit()

    # Set DATABASE_URL so app code uses the test DB
    os.environ["DATABASE_URL"] = _TEST_DB_URL


def pytest_unconfigure(config):
    """Dispose of the test engine."""
    global _pg_engine
    if _pg_engine is not None:
        _pg_engine.dispose()
        _pg_engine = None


@pytest.fixture(scope="session")
def postgis_engine():
    """Return the session-scoped PostGIS engine."""
    from app.database import Base
    from app import models  # noqa: F401 — populate Base.metadata

    Base.metadata.create_all(bind=_pg_engine)
    return _pg_engine


@pytest.fixture(scope="session")
def SessionFactory(postgis_engine):
    """Return a sessionmaker bound to the PostGIS engine."""
    return sessionmaker(bind=postgis_engine, expire_on_commit=False)


@pytest.fixture()
def db_session(postgis_engine) -> Generator[Session, None, None]:
    """Provide a clean database session that rolls back after each test."""
    from app.database import Base

    # Truncate all tables for a clean slate
    with postgis_engine.connect() as cleanup_conn:
        for table in reversed(Base.metadata.sorted_tables):
            cleanup_conn.execute(text(f"TRUNCATE TABLE {table.name} CASCADE"))
        cleanup_conn.commit()

    connection = postgis_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# Geometry factories
# ---------------------------------------------------------------------------


class GeoFactory:
    """Deterministic geometry helpers for tests."""

    # --- Points ---
    SEATTLE_CENTER = Point(-122.3321, 47.6062)
    PITTSBURGH_CENTER = Point(-79.9959, 40.4406)
    CHICAGO_CENTER = Point(-87.6298, 41.8781)

    @staticmethod
    def make_linestring(coords: list[tuple[float, float]] | None = None) -> LineString:
        """Create a LineString from coordinate pairs or a sensible default."""
        if coords is None:
            coords = [
                (-122.3321, 47.6062),
                (-122.3325, 47.6070),
                (-122.3330, 47.6075),
                (-122.3340, 47.6080),
            ]
        return LineString(coords)

    @staticmethod
    def make_street_segment(
        start: tuple[float, float] = (-122.3321, 47.6062),
        end: tuple[float, float] = (-122.3340, 47.6080),
        num_points: int = 4,
    ) -> LineString:
        """Create a street-like LineString between two points."""
        dx = (end[0] - start[0]) / (num_points - 1)
        dy = (end[1] - start[1]) / (num_points - 1)
        coords = [(start[0] + dx * i, start[1] + dy * i) for i in range(num_points)]
        return LineString(coords)

    @staticmethod
    def make_gps_trace(
        street: LineString,
        offset_meters: float = 5.0,
    ) -> LineString:
        """
        Create a GPS trace that loosely follows a street LineString.

        The offset is approximate (degrees latitude ~111km, so offset_meters
        translates to a small degree offset for testing).
        """
        # Rough conversion: 1 degree lat ≈ 111_000 m
        offset_deg = offset_meters / 111_000
        coords = [(x + offset_deg, y) for x, y in street.coords]
        return LineString(coords)

    @staticmethod
    def make_polygon(
        center: tuple[float, float] = (-122.3321, 47.6062),
        size_deg: float = 0.01,
    ) -> Polygon:
        """Create a square polygon centered on a point."""
        cx, cy = center
        half = size_deg / 2
        return Polygon(
            [
                (cx - half, cy - half),
                (cx + half, cy - half),
                (cx + half, cy + half),
                (cx - half, cy + half),
                (cx - half, cy - half),
            ]
        )

    @staticmethod
    def make_neighborhood_boundary(
        center: tuple[float, float] = (-122.3321, 47.6062),
        size_deg: float = 0.005,
    ) -> MultiPolygon:
        """Create a MultiPolygon neighborhood boundary."""
        poly = GeoFactory.make_polygon(center, size_deg)
        return MultiPolygon([poly])

    @staticmethod
    def make_city_boundary(
        center: tuple[float, float] = (-122.3321, 47.6062),
        size_deg: float = 0.1,
    ) -> MultiPolygon:
        """Create a MultiPolygon city boundary."""
        poly = GeoFactory.make_polygon(center, size_deg)
        return MultiPolygon([poly])


@pytest.fixture()
def geo():
    """Provide a GeoFactory instance."""
    return GeoFactory()


# ---------------------------------------------------------------------------
# Data factories
# ---------------------------------------------------------------------------


def make_user_data(**overrides: Any) -> dict[str, Any]:
    """Return a dict of default User field values, with optional overrides."""
    defaults: dict[str, Any] = {
        "strava_athlete_id": 12345678,
        "display_name": "Test Runner",
        "profile_image_url": None,
        "access_token_encrypted": "encrypted_access_token_placeholder",
        "refresh_token_encrypted": "encrypted_refresh_token_placeholder",
        "token_expires_at": datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=6),
        "strava_scope": "activity:read_all",
        "sync_status": "idle",
    }
    defaults.update(overrides)
    return defaults


def make_activity_data(**overrides: Any) -> dict[str, Any]:
    """Return a dict of default Activity field values, with optional overrides."""
    defaults: dict[str, Any] = {
        "strava_activity_id": 9876543210,
        "name": "Morning Run",
        "sport_type": "Run",
        "start_date": datetime.datetime(2025, 1, 15, 8, 0, 0, tzinfo=datetime.UTC),
        "distance_meters": 5000.0,
        "duration_seconds": 1800,
        "moving_time_seconds": 1750,
        "summary_polyline": None,
        "detailed_polyline": None,
        "has_gps": True,
        "is_on_street": True,
        "import_status": "pending",
    }
    defaults.update(overrides)
    return defaults


@pytest.fixture()
def user_data():
    """Provide a default user data factory."""
    return make_user_data


@pytest.fixture()
def activity_data():
    """Provide a default activity data factory."""
    return make_activity_data
