"""
Integration tests for the routes API endpoints.

Tests:
- POST /routes/suggest -> validates input, delegates to planner
- GET  /routes/history -> returns past suggestions
"""

import datetime

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from geoalchemy2.shape import from_shape
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models.city import City
from app.models.neighborhood import Neighborhood
from app.models.route import RouteSuggestion
from app.models.user import User


# ---------------------------------------------------------------------------
# Self-contained test engine (avoids SQLite cross-thread errors)
# ---------------------------------------------------------------------------


def _make_test_session():
    """Create an in-memory SQLite session with SpatiaLite for integration tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    _spatialite_loaded = False

    @event.listens_for(engine, "connect")
    def _load_spatialite(dbapi_conn, connection_record):
        nonlocal _spatialite_loaded
        dbapi_conn.enable_load_extension(True)
        for lib_name in ("mod_spatialite", "libspatialite"):
            try:
                dbapi_conn.load_extension(lib_name)
                _spatialite_loaded = True
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

    if not _spatialite_loaded:
        pytest.skip("SpatiaLite extension not available")

    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    return TestSession


def _get_test_app():
    """Create the FastAPI app with test DB override."""
    from app.main import create_app

    test_app = create_app()
    TestSession = _make_test_session()

    def override_get_db():
        session = TestSession()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    test_app.dependency_overrides[get_db] = override_get_db
    return test_app, TestSession


def _seed_data(session):
    """Seed DB with city, neighborhood, user."""
    poly = Polygon([
        (-122.40, 47.55), (-122.25, 47.55), (-122.25, 47.65),
        (-122.40, 47.65), (-122.40, 47.55),
    ])
    city = City(
        name="Seattle",
        state="Washington",
        country="US",
        boundary=from_shape(MultiPolygon([poly]), srid=4326),
        projected_crs="EPSG:2926",
        total_street_segments=10,
        total_street_length_m=2000.0,
    )
    session.add(city)
    session.flush()

    npoly = Polygon([
        (-122.35, 47.60), (-122.32, 47.60), (-122.32, 47.62),
        (-122.35, 47.62), (-122.35, 47.60),
    ])
    neighborhood = Neighborhood(
        city_id=city.id,
        name="Capitol Hill",
        boundary=from_shape(MultiPolygon([npoly]), srid=4326),
        total_street_segments=5,
        total_street_length_m=1000.0,
    )
    session.add(neighborhood)
    session.flush()

    user = User(
        strava_athlete_id=12345,
        display_name="Test Runner",
        access_token_encrypted="tok",
        refresh_token_encrypted="rtok",
        token_expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=6),
        strava_scope="activity:read_all",
        sync_status="idle",
    )
    session.add(user)
    session.commit()

    return {"city": city, "neighborhood": neighborhood, "user": user}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRouteSuggestEndpoint:
    """POST /routes/suggest."""

    def test_invalid_city_returns_404(self):
        app, SessionCls = _get_test_app()
        session = SessionCls()
        _seed_data(session)
        session.close()

        with TestClient(app) as client:
            resp = client.post("/api/v1/routes/suggest", json={
                "city_id": 9999,
                "start_point": {"lng": -122.33, "lat": 47.61},
                "distance_meters": 3000,
            })
        assert resp.status_code == 404

    def test_missing_start_point_returns_422(self):
        app, SessionCls = _get_test_app()
        session = SessionCls()
        entities = _seed_data(session)
        city_id = entities["city"].id
        session.close()

        with TestClient(app) as client:
            resp = client.post("/api/v1/routes/suggest", json={
                "city_id": city_id,
                "distance_meters": 3000,
            })
        assert resp.status_code == 422

    def test_missing_lat_lng_returns_400(self):
        app, SessionCls = _get_test_app()
        session = SessionCls()
        entities = _seed_data(session)
        city_id = entities["city"].id
        session.close()

        with TestClient(app) as client:
            resp = client.post("/api/v1/routes/suggest", json={
                "city_id": city_id,
                "start_point": {"x": 0, "y": 0},
                "distance_meters": 3000,
            })
        assert resp.status_code == 400

    @patch("app.api.routes.RoutePlannerService")
    def test_successful_suggest_returns_route(self, MockPlanner):
        app, SessionCls = _get_test_app()
        session = SessionCls()
        entities = _seed_data(session)
        city_id = entities["city"].id
        session.close()

        mock_instance = MockPlanner.return_value
        mock_instance.suggest = AsyncMock(return_value={
            "route": {
                "id": 1,
                "distance_meters": 3000,
                "estimated_duration_seconds": 1800,
                "untraveled_distance_meters": 2100,
                "untraveled_ratio": 0.70,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[-122.33, 47.61], [-122.34, 47.62]],
                },
            },
            "segments": [],
            "message": "Route generated successfully",
        })

        with TestClient(app) as client:
            resp = client.post("/api/v1/routes/suggest", json={
                "city_id": city_id,
                "start_point": {"lng": -122.33, "lat": 47.61},
                "distance_meters": 3000,
            })
        assert resp.status_code == 200
        data = resp.json()
        assert "route" in data
        assert data["route"]["distance_meters"] == 3000
        assert data["route"]["untraveled_ratio"] == 0.70


class TestRouteHistoryEndpoint:
    """GET /routes/history."""

    def test_empty_history(self):
        app, SessionCls = _get_test_app()
        session = SessionCls()
        _seed_data(session)
        session.close()

        with TestClient(app) as client:
            resp = client.get("/api/v1/routes/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "routes" in data
        assert data["routes"] == []

    def test_returns_past_suggestions(self):
        app, SessionCls = _get_test_app()
        session = SessionCls()
        entities = _seed_data(session)

        suggestion = RouteSuggestion(
            user_id=entities["user"].id,
            city_id=entities["city"].id,
            neighborhood_id=entities["neighborhood"].id,
            start_point=from_shape(Point(-122.33, 47.61), srid=4326),
            route_geometry=from_shape(
                LineString([(-122.33, 47.61), (-122.34, 47.62)]), srid=4326
            ),
            distance_meters=2950,
            estimated_duration_seconds=1770,
            requested_distance_meters=3000,
            untraveled_distance_meters=1917.5,
            untraveled_ratio=0.65,
            created_at=datetime.datetime.now(datetime.UTC),
        )
        session.add(suggestion)
        session.commit()
        session.close()

        with TestClient(app) as client:
            resp = client.get("/api/v1/routes/history")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["routes"]) == 1
        assert data["routes"][0]["city_name"] == "Seattle"
        assert data["routes"][0]["neighborhood_name"] == "Capitol Hill"
