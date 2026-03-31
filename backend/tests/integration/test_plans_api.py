"""
Integration tests for the Plans & Goals API.

Tests:
- POST /plans/neighborhood → create plan (mocked OSRM)
- GET  /plans              → list plans
- GET  /plans/{id}         → get plan detail
- DELETE /plans/{id}       → remove plan
- POST /plans/goals        → create goal (mocked OSRM)
- GET  /plans/goals        → list goals
- GET  /plans/goals/{id}   → get goal detail
"""

import datetime

from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from geoalchemy2.shape import from_shape
from shapely.geometry import LineString, MultiPolygon, Point, Polygon

from app.models.city import City
from app.models.neighborhood import Neighborhood
from app.models.street import StreetSegment
from app.models.user import User
from tests.integration.conftest import _make_test_session, _get_test_app as _get_base_app


def _get_test_app():
    return _get_base_app()


def _seed_city_and_neighborhood(session):
    """Seed a city + neighborhood + streets for plan tests."""
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
        total_street_segments=5,
        total_street_length_m=1000.0,
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
        total_street_segments=3,
        total_street_length_m=600.0,
    )
    session.add(neighborhood)
    session.flush()

    # Seed a few street segments
    for i in range(3):
        lng = -122.34 + i * 0.005
        st = StreetSegment(
            city_id=city.id,
            neighborhood_id=neighborhood.id,
            name=f"Street {i}",
            highway_type="residential",
            osm_way_id=1000 + i,
            osm_node_start=2000 + i,
            osm_node_end=3000 + i,
            geometry=from_shape(LineString([(lng, 47.61), (lng, 47.615)]), srid=4326),
            length_meters=200.0,
        )
        session.add(st)
    session.flush()
    session.commit()

    return city, neighborhood


# Mock OSRM responses
_OSRM_TRIP_RESPONSE = {
    "distance": 3000.0,
    "duration": 1500.0,
    "geometry": {
        "type": "LineString",
        "coordinates": [
            [-122.34, 47.61], [-122.335, 47.615],
            [-122.33, 47.61], [-122.34, 47.61],
        ],
    },
}

_OSRM_NEAREST_RESPONSE = {
    "location": [-122.34, 47.61],
    "distance": 5.0,
    "name": "Street 0",
}


def _seed_start_point(session, user):
    """Seed a UserStartPoint and return its id."""
    from app.models.start_point import UserStartPoint
    sp = UserStartPoint(
        user_id=user.id,
        name="Home",
        point=from_shape(Point(-122.33, 47.61), srid=4326),
        is_default=True,
    )
    session.add(sp)
    session.commit()
    return sp.id


def _mock_osrm():
    """Patch both check_osrm_available and the OSRM client methods."""
    return [
        patch("app.services.routing.check_osrm_available", new_callable=AsyncMock, return_value=True),
        patch("app.services.routing.OSRMClient.trip", new_callable=AsyncMock, return_value=_OSRM_TRIP_RESPONSE),
        patch("app.services.routing.OSRMClient.nearest", new_callable=AsyncMock, return_value=_OSRM_NEAREST_RESPONSE),
    ]


class TestPlanCreate:
    """POST /plans/neighborhood."""

    def test_create_plan_returns_201(self):
        app, SessionCls, user = _get_test_app()
        session = SessionCls()
        city, neighborhood = _seed_city_and_neighborhood(session)
        sp_id = _seed_start_point(session, user)
        session.close()

        patches = _mock_osrm()
        for p in patches:
            p.start()
        try:
            with TestClient(app) as client:
                resp = client.post("/api/v1/plans/neighborhood", json={
                    "neighborhood_id": neighborhood.id,
                    "city_id": city.id,
                    "preferred_route_distance_m": 3000,
                    "start_point_id": sp_id,
                })
            assert resp.status_code == 201
            data = resp.json()
            assert data["neighborhood_name"] == "Capitol Hill"
            assert data["city_id"] == city.id
            assert data["status"] in ("ready", "failed", "generating")
            assert "routes" in data
        finally:
            for p in patches:
                p.stop()

    def test_invalid_neighborhood_returns_404(self):
        app, SessionCls, user = _get_test_app()
        session = SessionCls()
        city, _ = _seed_city_and_neighborhood(session)
        sp_id = _seed_start_point(session, user)
        session.close()

        patches = _mock_osrm()
        for p in patches:
            p.start()
        try:
            with TestClient(app) as client:
                resp = client.post("/api/v1/plans/neighborhood", json={
                    "neighborhood_id": 99999,
                    "city_id": city.id,
                    "preferred_route_distance_m": 3000,
                    "start_point_id": sp_id,
                })
            assert resp.status_code == 404
        finally:
            for p in patches:
                p.stop()

    def test_invalid_city_returns_404(self):
        app, SessionCls, user = _get_test_app()
        session = SessionCls()
        _, neighborhood = _seed_city_and_neighborhood(session)
        sp_id = _seed_start_point(session, user)
        session.close()

        patches = _mock_osrm()
        for p in patches:
            p.start()
        try:
            with TestClient(app) as client:
                resp = client.post("/api/v1/plans/neighborhood", json={
                    "neighborhood_id": neighborhood.id,
                    "city_id": 99999,
                    "preferred_route_distance_m": 3000,
                    "start_point_id": sp_id,
                })
            assert resp.status_code == 404
        finally:
            for p in patches:
                p.stop()


class TestPlanList:
    """GET /plans."""

    def test_empty_list(self):
        app, _, _ = _get_test_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/plans")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_after_create(self):
        app, SessionCls, user = _get_test_app()
        session = SessionCls()
        city, neighborhood = _seed_city_and_neighborhood(session)
        sp_id = _seed_start_point(session, user)
        session.close()

        patches = _mock_osrm()
        for p in patches:
            p.start()
        try:
            with TestClient(app) as client:
                client.post("/api/v1/plans/neighborhood", json={
                    "neighborhood_id": neighborhood.id,
                    "city_id": city.id,
                    "preferred_route_distance_m": 3000,
                    "start_point_id": sp_id,
                })
                resp = client.get("/api/v1/plans")

            assert resp.status_code == 200
            plans = resp.json()
            assert len(plans) >= 1
            assert plans[0]["neighborhood_name"] == "Capitol Hill"
        finally:
            for p in patches:
                p.stop()

    def test_standalone_plan_has_null_goal_id(self):
        """Plans created directly (not from a goal) should have goal_id=null."""
        app, SessionCls, user = _get_test_app()
        session = SessionCls()
        city, neighborhood = _seed_city_and_neighborhood(session)

        # Seed a start point (required by CoveragePlanCreate)
        from app.models.start_point import UserStartPoint
        start_pt = UserStartPoint(
            user_id=user.id,
            name="Home",
            point=from_shape(Point(-122.33, 47.61), srid=4326),
            is_default=True,
        )
        session.add(start_pt)
        session.commit()
        sp_id = start_pt.id
        session.close()

        patches = _mock_osrm()
        for p in patches:
            p.start()
        try:
            with TestClient(app) as client:
                create_resp = client.post("/api/v1/plans/neighborhood", json={
                    "neighborhood_id": neighborhood.id,
                    "city_id": city.id,
                    "preferred_route_distance_m": 3000,
                    "start_point_id": sp_id,
                })
                assert create_resp.status_code == 201, f"Plan create failed: {create_resp.json()}"
                resp = client.get("/api/v1/plans")

            plans = resp.json()
            assert len(plans) >= 1
            assert "goal_id" in plans[0]
            assert plans[0]["goal_id"] is None
        finally:
            for p in patches:
                p.stop()


class TestPlanGetAndRoutes:
    """GET /plans/{id}, PATCH complete route, DELETE."""

    def _create_plan(self, client, city_id, neighborhood_id, start_point_id):
        resp = client.post("/api/v1/plans/neighborhood", json={
            "neighborhood_id": neighborhood_id,
            "city_id": city_id,
            "preferred_route_distance_m": 3000,
            "start_point_id": start_point_id,
        })
        assert resp.status_code == 201
        return resp.json()

    def test_get_plan_by_id(self):
        app, SessionCls, user = _get_test_app()
        session = SessionCls()
        city, neighborhood = _seed_city_and_neighborhood(session)
        sp_id = _seed_start_point(session, user)
        session.close()

        patches = _mock_osrm()
        for p in patches:
            p.start()
        try:
            with TestClient(app) as client:
                plan = self._create_plan(client, city.id, neighborhood.id, sp_id)
                resp = client.get(f"/api/v1/plans/{plan['id']}")
            assert resp.status_code == 200
            assert resp.json()["id"] == plan["id"]
        finally:
            for p in patches:
                p.stop()

    def test_get_nonexistent_plan_returns_404(self):
        app, _, _ = _get_test_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/plans/99999")
        assert resp.status_code == 404

    def test_delete_plan(self):
        app, SessionCls, user = _get_test_app()
        session = SessionCls()
        city, neighborhood = _seed_city_and_neighborhood(session)
        sp_id = _seed_start_point(session, user)
        session.close()

        patches = _mock_osrm()
        for p in patches:
            p.start()
        try:
            with TestClient(app) as client:
                plan = self._create_plan(client, city.id, neighborhood.id, sp_id)
                resp = client.delete(f"/api/v1/plans/{plan['id']}")
                assert resp.status_code == 204

                # Verify it's gone
                resp = client.get(f"/api/v1/plans/{plan['id']}")
                assert resp.status_code == 404
        finally:
            for p in patches:
                p.stop()


class TestGoals:
    """POST/GET /plans/goals."""

    def test_create_goal_returns_201(self):
        app, SessionCls, user = _get_test_app()
        session = SessionCls()
        city, neighborhood = _seed_city_and_neighborhood(session)
        session.close()

        patches = _mock_osrm()
        for p in patches:
            p.start()
        try:
            with TestClient(app) as client:
                resp = client.post("/api/v1/plans/goals", json={
                    "city_id": city.id,
                    "target_coverage_pct": 50.0,
                    "preferred_route_distance_m": 3000,
                })
            assert resp.status_code == 201
            data = resp.json()
            assert data["city_id"] == city.id
            assert data["target_coverage_pct"] == 50.0
            assert data["status"] in ("analyzing", "ready", "completed")
        finally:
            for p in patches:
                p.stop()

    def test_list_goals_empty(self):
        app, _, _ = _get_test_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/plans/goals")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_goal_by_id(self):
        app, SessionCls, user = _get_test_app()
        session = SessionCls()
        city, neighborhood = _seed_city_and_neighborhood(session)
        session.close()

        patches = _mock_osrm()
        for p in patches:
            p.start()
        try:
            with TestClient(app) as client:
                create_resp = client.post("/api/v1/plans/goals", json={
                    "city_id": city.id,
                    "target_coverage_pct": 50.0,
                    "preferred_route_distance_m": 3000,
                })
                goal_id = create_resp.json()["id"]

                resp = client.get(f"/api/v1/plans/goals/{goal_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == goal_id
            assert "neighborhoods" in data
        finally:
            for p in patches:
                p.stop()

    def test_goal_nonexistent_returns_404(self):
        app, _, _ = _get_test_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/plans/goals/99999")
        assert resp.status_code == 404

    def test_invalid_city_returns_404(self):
        app, _, _ = _get_test_app()

        patches = _mock_osrm()
        for p in patches:
            p.start()
        try:
            with TestClient(app) as client:
                resp = client.post("/api/v1/plans/goals", json={
                    "city_id": 99999,
                    "target_coverage_pct": 50.0,
                    "preferred_route_distance_m": 3000,
                })
            assert resp.status_code == 404
        finally:
            for p in patches:
                p.stop()
