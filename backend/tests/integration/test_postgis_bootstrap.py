"""
Integration tests for PostGIS database operations (T016-T020).

Verifies that city bootstrap patterns, spatial queries, neighborhood
assignment, concurrent access, and end-to-end API queries work correctly
against PostgreSQL + PostGIS.
"""

import datetime
import threading
import time

import pytest
from geoalchemy2 import functions as gfunc
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import LineString, MultiPolygon, Polygon
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.city import City
from app.models.coverage import UserStreetCoverage
from app.models.neighborhood import Neighborhood
from app.models.street import StreetSegment
from app.models.user import User


class TestPostGISCityInserts:
    """T016: Verify city and street inserts with WKT geometries on PostGIS."""

    def test_city_boundary_insert_and_spatial_query(self, db_session):
        poly = Polygon([
            (-122.40, 47.55), (-122.25, 47.55), (-122.25, 47.65),
            (-122.40, 47.65), (-122.40, 47.55),
        ])
        city = City(
            name="Seattle", state="WA", country="US",
            boundary=from_shape(MultiPolygon([poly]), srid=4326),
            projected_crs="EPSG:2926",
        )
        db_session.add(city)
        db_session.flush()

        assert city.id is not None
        shape = to_shape(city.boundary)
        assert shape.geom_type == "MultiPolygon"

    def test_bulk_street_segment_insert(self, db_session):
        poly = Polygon([(-122.40, 47.55), (-122.25, 47.55), (-122.25, 47.65),
                        (-122.40, 47.65), (-122.40, 47.55)])
        city = City(name="Seattle", state="WA", country="US",
                    boundary=from_shape(MultiPolygon([poly]), srid=4326),
                    projected_crs="EPSG:2926")
        db_session.add(city)
        db_session.flush()

        streets = []
        for i in range(100):
            lng = -122.33 + (i * 0.0001)
            geom = LineString([(lng, 47.60), (lng, 47.61)])
            streets.append(StreetSegment(
                city_id=city.id, osm_way_id=1000 + i,
                osm_node_start=i * 2, osm_node_end=i * 2 + 1,
                name=f"Test St {i}", highway_type="residential",
                geometry=from_shape(geom, srid=4326), length_meters=1113.0,
            ))
        db_session.add_all(streets)
        db_session.flush()

        count = db_session.query(StreetSegment).filter_by(city_id=city.id).count()
        assert count == 100

    def test_gist_bbox_spatial_query(self, db_session):
        poly = Polygon([(-122.40, 47.55), (-122.25, 47.55), (-122.25, 47.65),
                        (-122.40, 47.65), (-122.40, 47.55)])
        city = City(name="Seattle", state="WA", country="US",
                    boundary=from_shape(MultiPolygon([poly]), srid=4326),
                    projected_crs="EPSG:2926")
        db_session.add(city)
        db_session.flush()

        for i in range(50):
            lng = -122.33 + (i * 0.0001)
            geom = LineString([(lng, 47.60), (lng, 47.61)])
            db_session.add(StreetSegment(
                city_id=city.id, osm_way_id=3000 + i,
                osm_node_start=i * 2, osm_node_end=i * 2 + 1,
                name=f"St {i}", highway_type="residential",
                geometry=from_shape(geom, srid=4326), length_meters=1113.0,
            ))
        db_session.flush()

        bbox = gfunc.ST_MakeEnvelope(-122.335, 47.59, -122.325, 47.62, 4326)
        matches = db_session.query(StreetSegment).filter(
            StreetSegment.geometry.intersects(bbox)
        ).count()
        assert matches > 0


class TestPostGISNeighborhoodAssignment:
    """T017: Verify neighborhood street assignment via ST_Within + ST_Centroid."""

    def test_street_assignment_with_postgis_spatial_ops(self, db_session):
        poly = Polygon([(-122.40, 47.55), (-122.25, 47.55), (-122.25, 47.65),
                        (-122.40, 47.65), (-122.40, 47.55)])
        city = City(name="Seattle", state="WA", country="US",
                    boundary=from_shape(MultiPolygon([poly]), srid=4326),
                    projected_crs="EPSG:2926")
        db_session.add(city)
        db_session.flush()

        npoly = Polygon([(-122.35, 47.59), (-122.31, 47.59), (-122.31, 47.63),
                         (-122.35, 47.63), (-122.35, 47.59)])
        nb = Neighborhood(city_id=city.id, name="Capitol Hill",
                          boundary=from_shape(MultiPolygon([npoly]), srid=4326))
        db_session.add(nb)
        db_session.flush()

        # Add streets inside the neighborhood
        for i in range(10):
            lng = -122.33 + (i * 0.001)
            geom = LineString([(lng, 47.60), (lng, 47.61)])
            db_session.add(StreetSegment(
                city_id=city.id, osm_way_id=4000 + i,
                osm_node_start=i * 2, osm_node_end=i * 2 + 1,
                name=f"St {i}", highway_type="residential",
                geometry=from_shape(geom, srid=4326), length_meters=200.0,
            ))
        db_session.flush()

        # Run the PostGIS spatial assignment query
        bounds = npoly.bounds
        result = db_session.execute(text(
            "UPDATE street_segments SET neighborhood_id = :nb_id "
            "WHERE city_id = :city_id "
            "AND neighborhood_id IS NULL "
            "AND geometry && ST_MakeEnvelope(:minx, :miny, :maxx, :maxy, 4326) "
            "AND ST_Within(ST_Centroid(geometry), ST_GeomFromText(:nb_wkt, 4326))"
        ), {
            "nb_id": nb.id, "city_id": city.id,
            "minx": bounds[0], "miny": bounds[1],
            "maxx": bounds[2], "maxy": bounds[3],
            "nb_wkt": MultiPolygon([npoly]).wkt,
        })
        assigned = result.rowcount
        assert assigned > 0


class TestPostGISConcurrency:
    """T018: Verify concurrent read/write access without lock contention."""

    def test_concurrent_writer_and_readers(self, postgis_engine):
        """1 writer + 5 readers should complete without errors on PostGIS."""
        from app.database import Base
        Base.metadata.create_all(bind=postgis_engine)

        # Clean slate
        with postgis_engine.connect() as conn:
            for t in reversed(Base.metadata.sorted_tables):
                conn.execute(text(f"TRUNCATE TABLE {t.name} CASCADE"))
            conn.commit()

        errors = []

        def writer():
            try:
                with Session(postgis_engine) as session:
                    poly = Polygon([(-122.40, 47.55), (-122.25, 47.55),
                                    (-122.25, 47.65), (-122.40, 47.65), (-122.40, 47.55)])
                    city = City(name="ConcTest", state="WA", country="US",
                                boundary=from_shape(MultiPolygon([poly]), srid=4326),
                                projected_crs="EPSG:2926")
                    session.add(city)
                    session.commit()
                    for batch in range(3):
                        streets = []
                        for i in range(10):
                            idx = batch * 10 + i
                            geom = LineString([(-122.33 + idx * 0.0001, 47.60),
                                               (-122.33 + idx * 0.0001, 47.61)])
                            streets.append(StreetSegment(
                                city_id=city.id, osm_way_id=5000 + idx,
                                osm_node_start=idx * 2, osm_node_end=idx * 2 + 1,
                                name=f"St {idx}", highway_type="residential",
                                geometry=from_shape(geom, srid=4326), length_meters=200.0,
                            ))
                        session.add_all(streets)
                        session.commit()
                        time.sleep(0.02)
            except Exception as e:
                errors.append(f"writer: {e}")

        def reader(tid):
            try:
                with Session(postgis_engine) as session:
                    for _ in range(5):
                        session.query(City).all()
                        time.sleep(0.01)
            except Exception as e:
                errors.append(f"reader-{tid}: {e}")

        w = threading.Thread(target=writer)
        readers = [threading.Thread(target=reader, args=(i,)) for i in range(5)]
        w.start()
        for r in readers:
            r.start()
        w.join(timeout=15)
        for r in readers:
            r.join(timeout=5)

        assert errors == [], f"Concurrency errors: {errors}"


class TestLoadCitiesIncludesNeighborhoods:
    """Verify load_all_cities calls load_neighborhoods_for_city."""

    def test_load_city_triggers_neighborhood_loading(self, postgis_engine):
        """After load_city + the neighborhood step, neighborhoods should exist."""
        from unittest.mock import patch, MagicMock
        from app.database import Base
        from app.scripts.load_cities import load_all_cities

        Base.metadata.create_all(bind=postgis_engine)

        # Truncate for clean slate
        from sqlalchemy import text
        with postgis_engine.connect() as conn:
            for t in reversed(Base.metadata.sorted_tables):
                conn.execute(text(f"TRUNCATE TABLE {t.name} CASCADE"))
            conn.commit()

        # Mock the heavy OSM downloads but verify neighborhood loading is called
        mock_neighborhood_fn = MagicMock(return_value={"loaded": 5, "total": 5, "processed": 5, "assigned": 100, "unassigned": 0})

        with patch("app.scripts.load_cities.load_city") as mock_load_city, \
             patch("app.scripts.load_neighborhoods.load_neighborhoods_for_city", mock_neighborhood_fn):
            # Make load_city return a fake city object
            fake_city = MagicMock()
            fake_city.id = 1
            fake_city.name = "Seattle"
            mock_load_city.return_value = fake_city

            load_all_cities("Seattle")

        # Verify load_neighborhoods_for_city was called with the city
        assert mock_neighborhood_fn.called, "load_neighborhoods_for_city should be called after load_city"
        call_args = mock_neighborhood_fn.call_args
        assert call_args[0][1] == fake_city, "Should pass the city object to load_neighborhoods_for_city"

    def test_load_all_cities_source_contains_neighborhood_call(self):
        """Verify load_all_cities source code calls load_neighborhoods_for_city."""
        import inspect
        from app.scripts.load_cities import load_all_cities
        source = inspect.getsource(load_all_cities)
        assert "load_neighborhoods_for_city" in source, \
            "load_all_cities must call load_neighborhoods_for_city as part of the bootstrap"


class TestBootstrapScriptsUseFromShape:
    """Verify bootstrap scripts use from_shape() not raw EWKT strings for PostGIS."""

    def test_load_cities_uses_from_shape(self):
        """load_city must use from_shape() for city boundary, not raw EWKT strings."""
        import inspect
        from app.scripts.load_cities import load_city
        source = inspect.getsource(load_city)
        assert "from_shape(" in source, \
            "load_city must use from_shape() for PostGIS geometry columns"
        assert 'f"SRID=4326;{' not in source, \
            "load_city must not use raw EWKT strings — PostGIS requires from_shape()"

    def test_load_cities_street_segments_use_from_shape(self):
        """Street segment inserts must use from_shape() not raw EWKT strings."""
        import inspect
        from app.scripts.load_cities import load_city
        source = inspect.getsource(load_city)
        # The function should not have raw EWKT for geometry=
        lines_with_geometry = [l for l in source.split('\n') if 'geometry=' in l and 'SRID' in l]
        assert len(lines_with_geometry) == 0, \
            f"Found raw EWKT geometry assignments: {lines_with_geometry}"

    def test_load_neighborhoods_uses_from_shape(self):
        """load_neighborhoods_for_city must use from_shape() for neighborhood boundaries."""
        import inspect
        from app.scripts.load_neighborhoods import load_neighborhoods_for_city
        source = inspect.getsource(load_neighborhoods_for_city)
        assert "from_shape(" in source, \
            "load_neighborhoods_for_city must use from_shape() for PostGIS geometry columns"
        assert 'f"SRID=4326;{' not in source, \
            "load_neighborhoods_for_city must not use raw EWKT strings"

    def test_real_geometry_insert_roundtrip(self, db_session):
        """Insert a city + neighborhood using the same pattern as bootstrap scripts, verify roundtrip."""
        from geoalchemy2.shape import from_shape, to_shape
        from shapely.geometry import MultiPolygon, Polygon

        poly = Polygon([(-122.40, 47.55), (-122.25, 47.55), (-122.25, 47.65),
                        (-122.40, 47.65), (-122.40, 47.55)])
        boundary = MultiPolygon([poly])

        city = City(
            name="TestCity", state="WA", country="US",
            boundary=from_shape(boundary, srid=4326),
            projected_crs="EPSG:2926",
        )
        db_session.add(city)
        db_session.flush()

        nb = Neighborhood(
            city_id=city.id, name="TestHood",
            boundary=from_shape(boundary, srid=4326),
        )
        db_session.add(nb)
        db_session.flush()

        # Verify roundtrip
        loaded_city = db_session.query(City).filter_by(name="TestCity").one()
        loaded_nb = db_session.query(Neighborhood).filter_by(name="TestHood").one()
        assert to_shape(loaded_city.boundary).geom_type == "MultiPolygon"
        assert to_shape(loaded_nb.boundary).geom_type == "MultiPolygon"


class TestPostGISEndToEnd:
    """T020: End-to-end app API queries against PostGIS."""

    def test_cities_endpoint_on_empty_db(self):
        from fastapi.testclient import TestClient
        from tests.integration.conftest import _get_test_app

        app, _, _ = _get_test_app(with_auth=False)
        client = TestClient(app)

        resp = client.get("/api/v1/cities")
        assert resp.status_code == 200
        assert resp.json()["cities"] == []

    def test_cities_endpoint_with_seeded_data(self):
        from fastapi.testclient import TestClient
        from tests.integration.conftest import _get_test_app

        app, SessionCls, test_user = _get_test_app()
        session = SessionCls()

        poly = Polygon([(-122.40, 47.55), (-122.25, 47.55), (-122.25, 47.65),
                        (-122.40, 47.65), (-122.40, 47.55)])
        city = City(name="Seattle", state="WA", country="US",
                    boundary=from_shape(MultiPolygon([poly]), srid=4326),
                    projected_crs="EPSG:2926", total_street_segments=1)
        session.add(city)
        session.commit()
        session.close()

        client = TestClient(app)
        resp = client.get("/api/v1/cities")
        assert resp.status_code == 200
        cities = resp.json()["cities"]
        assert len(cities) == 1
        assert cities[0]["name"] == "Seattle"
