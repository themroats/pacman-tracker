"""
Integration tests for the cities API endpoints.

Tests:
- GET /cities -> list all cities
- GET /cities/{id}/neighborhoods -> list neighborhoods with coverage
- GET /cities/{id}/neighborhoods/{id}/boundary -> GeoJSON boundary
"""

import datetime

import pytest
from fastapi.testclient import TestClient
from geoalchemy2.shape import from_shape
from shapely.geometry import LineString, MultiPolygon, Polygon
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models.city import City
from app.models.coverage import UserStreetCoverage
from app.models.neighborhood import Neighborhood
from app.models.street import StreetSegment
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
    """Seed DB with city, neighborhood, street, user, and coverage."""
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
        total_street_segments=1,
        total_street_length_m=200.0,
    )
    session.add(neighborhood)
    session.flush()

    street = StreetSegment(
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
    session.add(street)
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
    session.flush()

    cov = UserStreetCoverage(
        user_id=user.id,
        street_segment_id=street.id,
        coverage_ratio=0.92,
        is_traveled=True,
        first_traveled_at=datetime.datetime(2025, 1, 15, tzinfo=datetime.UTC),
    )
    session.add(cov)
    session.commit()

    return {"city": city, "neighborhood": neighborhood, "street": street, "user": user}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestListCities:
    """GET /cities -- list all supported cities."""

    def test_returns_cities_list(self):
        app, SessionCls = _get_test_app()
        session = SessionCls()
        _seed_data(session)
        session.close()

        with TestClient(app) as client:
            resp = client.get("/api/v1/cities")
        assert resp.status_code == 200
        data = resp.json()
        assert "cities" in data
        assert len(data["cities"]) == 1
        city = data["cities"][0]
        assert city["name"] == "Seattle"
        assert city["state"] == "Washington"
        assert "total_street_segments" in city
        assert "total_neighborhoods" in city
        assert city["total_neighborhoods"] == 1

    def test_empty_database(self):
        app, _ = _get_test_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/cities")
        assert resp.status_code == 200
        assert resp.json()["cities"] == []


class TestListNeighborhoods:
    """GET /cities/{city_id}/neighborhoods -- neighborhoods with coverage."""

    def test_returns_neighborhoods(self):
        app, SessionCls = _get_test_app()
        session = SessionCls()
        entities = _seed_data(session)
        city_id = entities["city"].id
        session.close()

        with TestClient(app) as client:
            resp = client.get(f"/api/v1/cities/{city_id}/neighborhoods")
        assert resp.status_code == 200
        data = resp.json()
        assert "neighborhoods" in data
        assert len(data["neighborhoods"]) == 1
        n = data["neighborhoods"][0]
        assert n["name"] == "Capitol Hill"
        assert "coverage_percentage" in n

    def test_nonexistent_city_returns_404(self):
        app, SessionCls = _get_test_app()
        session = SessionCls()
        _seed_data(session)
        session.close()

        with TestClient(app) as client:
            resp = client.get("/api/v1/cities/9999/neighborhoods")
        assert resp.status_code == 404


class TestNeighborhoodBoundary:
    """GET /cities/{city_id}/neighborhoods/{id}/boundary -- GeoJSON."""

    def test_returns_geojson(self):
        app, SessionCls = _get_test_app()
        session = SessionCls()
        entities = _seed_data(session)
        city_id = entities["city"].id
        n_id = entities["neighborhood"].id
        session.close()

        with TestClient(app) as client:
            resp = client.get(f"/api/v1/cities/{city_id}/neighborhoods/{n_id}/boundary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] in ("Feature", "MultiPolygon", "Polygon")

    def test_nonexistent_neighborhood_returns_404(self):
        app, SessionCls = _get_test_app()
        session = SessionCls()
        entities = _seed_data(session)
        city_id = entities["city"].id
        session.close()

        with TestClient(app) as client:
            resp = client.get(f"/api/v1/cities/{city_id}/neighborhoods/9999/boundary")
        assert resp.status_code == 404
