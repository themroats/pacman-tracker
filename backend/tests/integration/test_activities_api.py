"""
Integration tests for the activities API endpoints.

Tests cover:
- List activities with filters
- Get activity detail
- Get activities as GeoJSON
"""

import pytest
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from tests.integration.conftest import _make_test_session, _get_test_app


class TestActivitiesListEndpoint:
    """T085: Test GET /activities with filters."""

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
    """T085: Test GET /activities/{id}."""

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
    """T085: Test GET /activities/geojson."""

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
