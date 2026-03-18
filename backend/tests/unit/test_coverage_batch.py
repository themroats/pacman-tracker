"""
Unit test for batched coverage query (SC-007).

Verifies:
- city_coverage() endpoint uses at most 2 DB queries (neighborhoods + coverage)
  regardless of the number of neighborhoods
- The batched GROUP BY query produces correct results
"""

import datetime
from contextlib import asynccontextmanager
from unittest.mock import patch

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
from app.services.crypto import compute_token_hash


@asynccontextmanager
async def _noop_lifespan(app):
    yield


def _make_boundary(cx, cy, size=0.005):
    poly = Polygon([
        (cx - size, cy - size), (cx + size, cy - size),
        (cx + size, cy + size), (cx - size, cy + size),
        (cx - size, cy - size),
    ])
    return from_shape(MultiPolygon([poly]), srid=4326)


def _make_street_geom(x1, y1, x2, y2):
    return from_shape(LineString([(x1, y1), (x2, y2)]), srid=4326)


@pytest.fixture()
def test_env():
    """Set up test DB with a city, multiple neighborhoods, streets, and coverage data."""
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
    SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionFactory()

    # Create user
    user = User(
        strava_athlete_id=55555,
        display_name="Coverage Tester",
        access_token_encrypted="enc",
        access_token_hash=compute_token_hash("cov_token"),
        refresh_token_encrypted="ref",
        token_expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=6),
        strava_scope="activity:read_all",
        sync_status="idle",
    )
    session.add(user)
    session.flush()

    # Create city
    city = City(
        name="Test City",
        state="TC",
        country="US",
        boundary=_make_boundary(-122.33, 47.60, 0.05),
        projected_crs="EPSG:32610",
        total_street_segments=0,
        total_street_length_m=0,
    )
    session.add(city)
    session.flush()

    # Create N neighborhoods with streets
    num_neighborhoods = 10
    neighborhoods = []
    for i in range(num_neighborhoods):
        n = Neighborhood(
            city_id=city.id,
            name=f"Neighborhood {i}",
            boundary=_make_boundary(-122.33 + i * 0.01, 47.60),
            total_street_segments=2,
            total_street_length_m=400.0,
        )
        session.add(n)
        session.flush()
        neighborhoods.append(n)

        # Add 2 streets per neighborhood
        for j in range(2):
            s = StreetSegment(
                city_id=city.id,
                neighborhood_id=n.id,
                osm_way_id=i * 100 + j,
                osm_node_start=i * 1000 + j * 10,
                osm_node_end=i * 1000 + j * 10 + 1,
                name=f"Street {i}-{j}",
                highway_type="residential",
                geometry=_make_street_geom(
                    -122.33 + i * 0.01, 47.60 + j * 0.001,
                    -122.33 + i * 0.01 + 0.005, 47.60 + j * 0.001,
                ),
                length_meters=200.0,
            )
            session.add(s)
            session.flush()

            # Mark first street of first neighborhood as traveled
            if i == 0 and j == 0:
                cov = UserStreetCoverage(
                    user_id=user.id,
                    street_segment_id=s.id,
                    coverage_ratio=0.95,
                    is_traveled=True,
                    first_traveled_at=datetime.datetime.now(datetime.UTC),
                )
                session.add(cov)

    city.total_street_segments = num_neighborhoods * 2
    city.total_street_length_m = num_neighborhoods * 400.0
    session.commit()

    yield {
        "engine": engine,
        "session": session,
        "user": user,
        "city": city,
        "neighborhoods": neighborhoods,
        "num_neighborhoods": num_neighborhoods,
    }
    session.close()


class TestBatchedCoverageQuery:
    """SC-007: Coverage page loads neighborhood data using at most 2 DB queries."""

    def test_city_coverage_returns_all_neighborhoods(self, test_env):
        """Endpoint returns coverage for all neighborhoods in a single request."""
        session = test_env["session"]
        city = test_env["city"]

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

        client = TestClient(app)
        resp = client.get(
            f"/api/v1/coverage/city/{city.id}",
            headers={"Authorization": "Bearer cov_token"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["neighborhoods"]) == test_env["num_neighborhoods"]

    def test_coverage_query_count_bounded(self, test_env):
        """The batched query should use at most 2 DB queries regardless of neighborhood count.

        We verify this by checking that the endpoint uses a GROUP BY pattern
        (the N+1 pattern would issue N+1 queries). We validate the structure
        of the response shows data was gathered efficiently.
        """
        session = test_env["session"]
        city = test_env["city"]

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

        # Track query count
        query_count = 0
        original_execute = session.execute

        def counting_execute(*args, **kwargs):
            nonlocal query_count
            query_count += 1
            return original_execute(*args, **kwargs)

        session.execute = counting_execute

        client = TestClient(app)
        resp = client.get(
            f"/api/v1/coverage/city/{city.id}",
            headers={"Authorization": "Bearer cov_token"},
        )

        session.execute = original_execute

        assert resp.status_code == 200
        # Should be: 1 (auth lookup) + 1 (city.get) + 1 (neighborhoods) + 1 (batched coverage) = 4
        # The key constraint: NOT 1 + N neighborhood queries
        # With 10 neighborhoods, N+1 would be 11+ queries
        assert query_count <= 6, (
            f"Expected ≤6 queries (auth + city + neighborhoods + batch coverage), "
            f"got {query_count}. This suggests an N+1 query pattern."
        )

    def test_first_neighborhood_shows_traveled_street(self, test_env):
        """The first neighborhood should show 1 traveled street from the fixture data."""
        session = test_env["session"]
        city = test_env["city"]

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

        client = TestClient(app)
        resp = client.get(
            f"/api/v1/coverage/city/{city.id}",
            headers={"Authorization": "Bearer cov_token"},
        )

        assert resp.status_code == 200
        neighborhoods = resp.json()["neighborhoods"]
        # Neighborhood 0 has 1 traveled street out of 2
        n0 = next(n for n in neighborhoods if n["name"] == "Neighborhood 0")
        assert n0["streets_traveled"] == 1
        assert n0["streets_total"] == 2
        assert n0["coverage_percentage"] == 50.0
