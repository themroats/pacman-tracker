"""
T088 -- Coverage API integration tests.

Tests:
- GET /coverage/city/{city_id}  -> city summary + neighborhoods
- GET /coverage/neighborhood/{neighborhood_id}  -> detail + boundary
- GET /coverage/neighborhood/{neighborhood_id}/streets  -> GeoJSON FeatureCollection
- GET /coverage/city/{city_id}/streets  -> GeoJSON with optional filters
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
    """Seed database with a city, neighborhood, streets, user and coverage records."""
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
        total_street_segments=2,
        total_street_length_m=400.0,
    )
    session.add(neighborhood)
    session.flush()

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
    session.add_all([street1, street2])
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
    session.add_all([cov1, cov2])
    session.commit()

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

    def test_returns_city_summary(self):
        app, SessionCls = _get_test_app()
        session = SessionCls()
        entities = _seed_data(session)
        city_id = entities["city"].id
        session.close()

        with TestClient(app) as client:
            resp = client.get(
                f"/api/v1/coverage/city/{city_id}",
                headers={"Authorization": "Bearer test"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "city" in data
        assert data["city"]["name"] == "Seattle"
        assert "neighborhoods" in data

    def test_city_not_found(self):
        app, SessionCls = _get_test_app()
        session = SessionCls()
        _seed_data(session)
        session.close()

        with TestClient(app) as client:
            resp = client.get(
                "/api/v1/coverage/city/9999",
                headers={"Authorization": "Bearer test"},
            )
        assert resp.status_code == 404


class TestNeighborhoodDetailEndpoint:
    """GET /api/v1/coverage/neighborhood/{neighborhood_id}"""

    def test_returns_neighborhood_detail(self):
        app, SessionCls = _get_test_app()
        session = SessionCls()
        entities = _seed_data(session)
        n_id = entities["neighborhood"].id
        session.close()

        with TestClient(app) as client:
            resp = client.get(
                f"/api/v1/coverage/neighborhood/{n_id}",
                headers={"Authorization": "Bearer test"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["neighborhood"]["name"] == "Capitol Hill"
        assert "boundary" in data


class TestNeighborhoodStreetsEndpoint:
    """GET /api/v1/coverage/neighborhood/{neighborhood_id}/streets"""

    def test_returns_geojson_feature_collection(self):
        app, SessionCls = _get_test_app()
        session = SessionCls()
        entities = _seed_data(session)
        n_id = entities["neighborhood"].id
        session.close()

        with TestClient(app) as client:
            resp = client.get(
                f"/api/v1/coverage/neighborhood/{n_id}/streets",
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

    def test_returns_all_streets(self):
        app, SessionCls = _get_test_app()
        session = SessionCls()
        entities = _seed_data(session)
        city_id = entities["city"].id
        n_id = entities["neighborhood"].id
        session.close()

        with TestClient(app) as client:
            resp = client.get(
                f"/api/v1/coverage/city/{city_id}/streets?neighborhood_id={n_id}",
                headers={"Authorization": "Bearer test"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 2

    def test_filter_by_status_traveled(self):
        app, SessionCls = _get_test_app()
        session = SessionCls()
        entities = _seed_data(session)
        city_id = entities["city"].id
        n_id = entities["neighborhood"].id
        session.close()

        with TestClient(app) as client:
            resp = client.get(
                f"/api/v1/coverage/city/{city_id}/streets?neighborhood_id={n_id}&status=traveled",
                headers={"Authorization": "Bearer test"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["features"]) == 1
        assert data["features"][0]["properties"]["is_traveled"] is True

    def test_filter_by_neighborhood(self):
        app, SessionCls = _get_test_app()
        session = SessionCls()
        entities = _seed_data(session)
        city_id = entities["city"].id
        n_id = entities["neighborhood"].id
        session.close()

        with TestClient(app) as client:
            resp = client.get(
                f"/api/v1/coverage/city/{city_id}/streets?neighborhood_id={n_id}",
                headers={"Authorization": "Bearer test"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["features"]) == 2
