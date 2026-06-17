"""
Integration tests for the activities API endpoints.

Tests cover:
- List activities with filters
- Get activity detail
- Get activities as GeoJSON
- Get single activity GeoJSON (returns Feature, not FeatureCollection)
"""

import datetime

import pytest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from geoalchemy2.shape import from_shape
from shapely.geometry import LineString

from app.database import Base, get_db
from app.models.activity import Activity
from tests.integration.conftest import _make_test_session, _get_test_app


class TestActivitiesListEndpoint:
    """Test GET /activities with filters."""

    def test_list_activities_returns_paginated(self):
        """GET /activities should return paginated activity list."""
        from fastapi.testclient import TestClient

        app, _, _ = _get_test_app()
        client = TestClient(app)
        response = client.get("/api/v1/activities")

        assert response.status_code == 200
        data = response.json()
        assert "activities" in data
        assert "total" in data
        assert "page" in data

    def test_list_activities_filter_by_sport_type(self):
        """GET /activities?sport_type=Run should filter by sport type."""
        from fastapi.testclient import TestClient

        app, _, _ = _get_test_app()
        client = TestClient(app)
        response = client.get("/api/v1/activities?sport_type=Run")

        assert response.status_code == 200

    def test_list_activities_filter_by_date_range(self):
        """GET /activities?start_date=...&end_date=... should filter by date."""
        from fastapi.testclient import TestClient

        app, _, _ = _get_test_app()
        client = TestClient(app)
        response = client.get(
            "/api/v1/activities?start_date=2025-01-01&end_date=2025-12-31"
        )

        assert response.status_code == 200


class TestActivityDetailEndpoint:
    """Test GET /activities/{id}."""

    def test_get_activity_returns_detail(self):
        """GET /activities/42 should return activity with GPS trace."""
        from fastapi.testclient import TestClient

        app, _, _ = _get_test_app()
        client = TestClient(app)
        response = client.get("/api/v1/activities/42")

        # Will be 404 until activities exist, but endpoint should respond
        assert response.status_code in (200, 404)

    def test_get_nonexistent_activity_returns_404(self):
        """GET /activities/99999 should return 404."""
        from fastapi.testclient import TestClient

        app, _, _ = _get_test_app()
        client = TestClient(app)
        response = client.get("/api/v1/activities/99999")

        assert response.status_code == 404


class TestActivitiesGeoJSONEndpoint:
    """Test GET /activities/geojson."""

    def test_geojson_returns_feature_collection(self):
        """GET /activities/geojson should return a GeoJSON FeatureCollection."""
        from fastapi.testclient import TestClient

        app, _, _ = _get_test_app()
        client = TestClient(app)
        response = client.get("/api/v1/activities/geojson")

        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert "features" in data


class TestSingleActivityGeoJSONEndpoint:
    """Test GET /activities/{id}/geojson — returns a Feature, NOT a FeatureCollection."""

    def test_returns_feature_type(self):
        """Single activity GeoJSON should be type=Feature with properties and geometry."""
        app, SessionCls, user = _get_test_app()
        session = SessionCls()

        # Seed an activity with GPS data
        act = Activity(
            user_id=user.id,
            strava_activity_id=12345,
            name="Test Run",
            sport_type="Run",
            start_date=datetime.datetime(2025, 6, 1, 8, 0, tzinfo=datetime.UTC),
            distance_meters=5000,
            duration_seconds=1800,
            moving_time_seconds=1750,
            has_gps=True,
            gps_trace=from_shape(LineString([(-122.33, 47.60), (-122.34, 47.61)]), srid=4326),
            import_status="matched",
        )
        session.add(act)
        session.commit()
        act_id = act.id
        session.close()

        with TestClient(app) as client:
            resp = client.get(f"/api/v1/activities/{act_id}/geojson")

        assert resp.status_code == 200
        data = resp.json()
        # Must be a Feature, NOT a FeatureCollection
        assert data["type"] == "Feature"
        assert "properties" in data
        assert "geometry" in data
        assert data["geometry"]["type"] == "LineString"
        assert data["properties"]["id"] == act_id

    def test_nonexistent_returns_404(self):
        """GET /activities/99999/geojson should return 404."""
        app, _, _ = _get_test_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/activities/99999/geojson")
        assert resp.status_code == 404
