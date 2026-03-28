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
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.models.city import City
from app.models.neighborhood import Neighborhood
from app.models.route import RouteSuggestion
from app.models.user import User
from tests.integration.conftest import _make_test_session, _get_test_app as _get_base_app


# ---------------------------------------------------------------------------
# Self-contained test engine
# ---------------------------------------------------------------------------


def _get_test_app():
    """Wrap shared _get_test_app to return (app, SessionFactory, test_user) tuple."""
    app, TestSession, test_user = _get_base_app()
    return app, TestSession, test_user


def _seed_data(session, user):
    """Seed DB with city, neighborhood for the given user."""
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

    session.commit()

    return {"city": city, "neighborhood": neighborhood, "user": user}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRouteSuggestEndpoint:
    """POST /routes/suggest."""

    def test_invalid_city_returns_404(self):
        app, SessionCls, test_user = _get_test_app()
        session = SessionCls()
        _seed_data(session, test_user)
        session.close()

        with TestClient(app) as client:
            resp = client.post("/api/v1/routes/suggest", json={
                "city_id": 9999,
                "start_point": {"lng": -122.33, "lat": 47.61},
                "distance_meters": 3000,
            })
        assert resp.status_code == 404

    def test_missing_start_point_returns_422(self):
        app, SessionCls, test_user = _get_test_app()
        session = SessionCls()
        entities = _seed_data(session, test_user)
        city_id = entities["city"].id
        session.close()

        with TestClient(app) as client:
            resp = client.post("/api/v1/routes/suggest", json={
                "city_id": city_id,
                "distance_meters": 3000,
            })
        assert resp.status_code == 422

    def test_missing_lat_lng_returns_400(self):
        app, SessionCls, test_user = _get_test_app()
        session = SessionCls()
        entities = _seed_data(session, test_user)
        city_id = entities["city"].id
        session.close()

        with TestClient(app) as client:
            resp = client.post("/api/v1/routes/suggest", json={
                "city_id": city_id,
                "start_point": {"x": 0, "y": 0},
                "distance_meters": 3000,
            })
        assert resp.status_code in (400, 422)

    @patch("app.api.routes.RoutePlannerService")
    def test_successful_suggest_returns_route(self, MockPlanner):
        app, SessionCls, test_user = _get_test_app()
        session = SessionCls()
        entities = _seed_data(session, test_user)
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

    @patch("app.api.routes.RoutePlannerService")
    def test_osrm_unavailable_returns_503(self, MockPlanner):
        app, SessionCls, test_user = _get_test_app()
        session = SessionCls()
        entities = _seed_data(session, test_user)
        city_id = entities["city"].id
        session.close()

        mock_instance = MockPlanner.return_value
        mock_instance.suggest = AsyncMock(return_value={
            "error": "OSRM_UNAVAILABLE",
            "message": "OSRM service is unavailable",
        })

        with TestClient(app) as client:
            resp = client.post("/api/v1/routes/suggest", json={
                "city_id": city_id,
                "start_point": {"lng": -122.33, "lat": 47.61},
                "distance_meters": 3000,
            })

        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "OSRM_UNAVAILABLE"


class TestRouteHistoryEndpoint:
    """GET /routes/history."""

    def test_empty_history(self):
        app, SessionCls, test_user = _get_test_app()
        session = SessionCls()
        _seed_data(session, test_user)
        session.close()

        with TestClient(app) as client:
            resp = client.get("/api/v1/routes/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "routes" in data
        assert data["routes"] == []

    def test_returns_past_suggestions(self):
        app, SessionCls, test_user = _get_test_app()
        session = SessionCls()
        entities = _seed_data(session, test_user)

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
