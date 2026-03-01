"""
T088 — Coverage API integration tests.

Tests:
- GET /coverage/city/{city_id}  → city summary + neighborhoods
- GET /coverage/neighborhood/{neighborhood_id}  → detail + boundary
- GET /coverage/neighborhood/{neighborhood_id}/streets  → GeoJSON FeatureCollection
- GET /coverage/city/{city_id}/streets  → GeoJSON with optional filters
"""

import datetime

import pytest
from fastapi.testclient import TestClient
from geoalchemy2.shape import from_shape
from shapely.geometry import LineString, MultiPolygon, Polygon

from app.database import Base, get_db
from app.main import create_app
from app.models.city import City
from app.models.coverage import UserStreetCoverage
from app.models.neighborhood import Neighborhood
from app.models.street import StreetSegment
from app.models.user import User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app_client(db_session):
    """TestClient wired to the test database session."""

    def _override_db():
        yield db_session

    application = create_app()
    application.dependency_overrides[get_db] = _override_db
    with TestClient(application) as client:
        yield client


@pytest.fixture()
def seeded_db(db_session):
    """Seed database with a city, neighborhood, streets, user and coverage records."""
    # Create tables
    Base.metadata.create_all(db_session.get_bind())

    # City
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
        total_street_segments=2,
        total_street_length_m=400.0,
    )
    db_session.add(city)
    db_session.flush()

    # Neighborhood
    npoly = Polygon([
        (-122.35, 47.60), (-122.32, 47.60), (-122.32, 47.62),
        (-122.35, 47.62), (-122.35, 47.60),
    ])
    neighborhood = Neighborhood(
        city_id=city.id,
        name="Capitol Hill",
        boundary=from_shape(MultiPolygon([npoly]), srid=4326),
        total_street_segments=2,
        total_street_length_m=400.0,
    )
    db_session.add(neighborhood)
    db_session.flush()

    # Streets
    street1 = StreetSegment(
        city_id=city.id,
        neighborhood_id=neighborhood.id,
        osm_way_id=100,
        osm_node_start=1,
        osm_node_end=2,
        name="E Pine St",
        highway_type="residential",
        geometry=from_shape(LineString([(-122.33, 47.60), (-122.33, 47.61)]), srid=4326),
        length_meters=200.0,
    )
    street2 = StreetSegment(
        city_id=city.id,
        neighborhood_id=neighborhood.id,
        osm_way_id=101,
        osm_node_start=3,
        osm_node_end=4,
        name="Broadway E",
        highway_type="tertiary",
        geometry=from_shape(LineString([(-122.32, 47.60), (-122.32, 47.61)]), srid=4326),
        length_meters=200.0,
    )
    db_session.add_all([street1, street2])
    db_session.flush()

    # User
    user = User(
        strava_athlete_id=12345,
        display_name="Test Runner",
        access_token_encrypted="tok",
        refresh_token_encrypted="rtok",
        token_expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=6),
        strava_scope="activity:read_all",
        sync_status="idle",
    )
    db_session.add(user)
    db_session.flush()

    # Coverage — street1 traveled, street2 not
    cov1 = UserStreetCoverage(
        user_id=user.id,
        street_segment_id=street1.id,
        coverage_ratio=0.92,
        is_traveled=True,
        first_traveled_at=datetime.datetime(2025, 1, 15, tzinfo=datetime.UTC),
    )
    cov2 = UserStreetCoverage(
        user_id=user.id,
        street_segment_id=street2.id,
        coverage_ratio=0.30,
        is_traveled=False,
    )
    db_session.add_all([cov1, cov2])
    db_session.flush()

    return {
        "city": city,
        "neighborhood": neighborhood,
        "street1": street1,
        "street2": street2,
        "user": user,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCityCoverageEndpoint:
    """GET /api/v1/coverage/city/{city_id}"""

    def test_returns_city_summary(self, app_client, seeded_db):
        city = seeded_db["city"]
        resp = app_client.get(
            f"/api/v1/coverage/city/{city.id}",
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "city" in data
        assert data["city"]["name"] == "Seattle"
        assert "neighborhoods" in data

    def test_city_not_found(self, app_client, seeded_db):
        resp = app_client.get(
            "/api/v1/coverage/city/9999",
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 404


class TestNeighborhoodDetailEndpoint:
    """GET /api/v1/coverage/neighborhood/{neighborhood_id}"""

    def test_returns_neighborhood_detail(self, app_client, seeded_db):
        n = seeded_db["neighborhood"]
        resp = app_client.get(
            f"/api/v1/coverage/neighborhood/{n.id}",
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["neighborhood"]["name"] == "Capitol Hill"
        assert "boundary" in data


class TestNeighborhoodStreetsEndpoint:
    """GET /api/v1/coverage/neighborhood/{neighborhood_id}/streets"""

    def test_returns_geojson_feature_collection(self, app_client, seeded_db):
        n = seeded_db["neighborhood"]
        resp = app_client.get(
            f"/api/v1/coverage/neighborhood/{n.id}/streets",
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 2
        props = {f["properties"]["name"] for f in data["features"]}
        assert "E Pine St" in props


class TestCityStreetsEndpoint:
    """GET /api/v1/coverage/city/{city_id}/streets"""

    def test_returns_all_streets(self, app_client, seeded_db):
        city = seeded_db["city"]
        resp = app_client.get(
            f"/api/v1/coverage/city/{city.id}/streets",
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 2

    def test_filter_by_status_traveled(self, app_client, seeded_db):
        city = seeded_db["city"]
        resp = app_client.get(
            f"/api/v1/coverage/city/{city.id}/streets?status=traveled",
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["features"]) == 1
        assert data["features"][0]["properties"]["is_traveled"] is True

    def test_filter_by_neighborhood(self, app_client, seeded_db):
        city = seeded_db["city"]
        n = seeded_db["neighborhood"]
        resp = app_client.get(
            f"/api/v1/coverage/city/{city.id}/streets?neighborhood_id={n.id}",
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["features"]) == 2
