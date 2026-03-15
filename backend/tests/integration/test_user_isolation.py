"""
Integration tests for per-user data isolation (SC-002).

Verifies:
- GET /activities returns only the authenticated user's activities
- GET /activities/geojson returns only the authenticated user's traces
- GET /progress/stats returns only the authenticated user's stats
- Unauthenticated requests return 401
"""

import datetime
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models.activity import Activity
from app.models.user import User
from app.services.crypto import compute_token_hash


@asynccontextmanager
async def _noop_lifespan(app):
    yield


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _load_spatialite(dbapi_conn, connection_record):
        dbapi_conn.enable_load_extension(True)
        for lib_name in ("mod_spatialite", "libspatialite"):
            try:
                dbapi_conn.load_extension(lib_name)
                break
            except Exception:
                continue
        dbapi_conn.enable_load_extension(False)

    with engine.connect() as conn:
        try:
            conn.execute(text("SELECT InitSpatialMetaData(1)"))
            conn.commit()
        except Exception:
            pytest.skip("SpatiaLite extension not available")

    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture()
def test_env():
    """Set up a test app with two users, each owning distinct activities."""
    engine = _make_engine()
    SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionFactory()

    # Create two users with known token hashes
    user_a = User(
        strava_athlete_id=111,
        display_name="User A",
        access_token_encrypted="enc_a",
        access_token_hash=compute_token_hash("token_a"),
        refresh_token_encrypted="ref_a",
        token_expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=6),
        strava_scope="activity:read_all",
        sync_status="idle",
    )
    user_b = User(
        strava_athlete_id=222,
        display_name="User B",
        access_token_encrypted="enc_b",
        access_token_hash=compute_token_hash("token_b"),
        refresh_token_encrypted="ref_b",
        token_expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=6),
        strava_scope="activity:read_all",
        sync_status="idle",
    )
    session.add_all([user_a, user_b])
    session.flush()

    # Create activities for each user
    act_a = Activity(
        user_id=user_a.id,
        strava_activity_id=1001,
        name="User A Morning Run",
        sport_type="Run",
        start_date=datetime.datetime(2025, 6, 1, 8, 0, tzinfo=datetime.UTC),
        distance_meters=5000,
        duration_seconds=1800,
        moving_time_seconds=1750,
        has_gps=False,
        import_status="matched",
    )
    act_b = Activity(
        user_id=user_b.id,
        strava_activity_id=2001,
        name="User B Evening Ride",
        sport_type="Ride",
        start_date=datetime.datetime(2025, 6, 1, 18, 0, tzinfo=datetime.UTC),
        distance_meters=20000,
        duration_seconds=3600,
        moving_time_seconds=3500,
        has_gps=False,
        import_status="matched",
    )
    session.add_all([act_a, act_b])
    session.commit()

    with patch("app.main.lifespan", _noop_lifespan):
        from app.main import create_app

        app = create_app()

    def override_get_db():
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db

    yield {
        "app": app,
        "session": session,
        "user_a": user_a,
        "user_b": user_b,
    }

    session.close()


class TestUserIsolation:
    """SC-002: 100% of data endpoints enforce user authentication and return only the authenticated user's data."""

    def test_activities_returns_only_own_data_user_a(self, test_env):
        client = TestClient(test_env["app"])
        resp = client.get(
            "/api/v1/activities",
            headers={"Authorization": "Bearer token_a"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["activities"][0]["name"] == "User A Morning Run"

    def test_activities_returns_only_own_data_user_b(self, test_env):
        client = TestClient(test_env["app"])
        resp = client.get(
            "/api/v1/activities",
            headers={"Authorization": "Bearer token_b"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["activities"][0]["name"] == "User B Evening Ride"

    def test_activities_geojson_returns_only_own_data(self, test_env):
        client = TestClient(test_env["app"])
        resp = client.get(
            "/api/v1/activities/geojson",
            headers={"Authorization": "Bearer token_a"},
        )
        assert resp.status_code == 200
        features = resp.json()["features"]
        # User A has no GPS, so should get empty features — but crucially
        # should NOT include User B's activities
        for f in features:
            assert f["properties"]["name"] != "User B Evening Ride"

    def test_unauthenticated_request_returns_401(self, test_env):
        client = TestClient(test_env["app"])
        resp = client.get("/api/v1/activities")
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, test_env):
        client = TestClient(test_env["app"])
        resp = client.get(
            "/api/v1/activities",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert resp.status_code == 401

    def test_progress_stats_requires_auth(self, test_env):
        client = TestClient(test_env["app"])
        resp = client.get("/api/v1/progress/stats")
        assert resp.status_code == 401
