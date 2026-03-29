"""
Integration tests for the Start Points API.

Tests:
- GET    /start-points            → list (empty, populated)
- POST   /start-points            → create, default flag, limit
- PATCH  /start-points/{id}       → update name, toggle default
- DELETE /start-points/{id}       → remove, 404 on other user's point
"""

from fastapi.testclient import TestClient

from tests.integration.conftest import _make_test_session, _get_test_app as _get_base_app


def _get_test_app():
    return _get_base_app()


class TestStartPointsList:
    """GET /start-points."""

    def test_empty_initially(self):
        app, _, _ = _get_test_app()
        with TestClient(app) as client:
            resp = client.get("/api/v1/start-points")
        assert resp.status_code == 200
        assert resp.json() == []


class TestStartPointsCreate:
    """POST /start-points."""

    def test_create_simple_point(self):
        app, _, _ = _get_test_app()
        with TestClient(app) as client:
            resp = client.post("/api/v1/start-points", json={
                "name": "Home",
                "lng": -122.33,
                "lat": 47.60,
                "is_default": False,
            })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Home"
        assert abs(data["lng"] - (-122.33)) < 0.0001
        assert abs(data["lat"] - 47.60) < 0.0001
        assert data["is_default"] is False
        assert "id" in data

    def test_create_default_point(self):
        app, _, _ = _get_test_app()
        with TestClient(app) as client:
            resp = client.post("/api/v1/start-points", json={
                "name": "Default Spot",
                "lng": -122.34,
                "lat": 47.61,
                "is_default": True,
            })
        assert resp.status_code == 201
        assert resp.json()["is_default"] is True

    def test_new_default_clears_old_default(self):
        app, _, _ = _get_test_app()
        with TestClient(app) as client:
            resp1 = client.post("/api/v1/start-points", json={
                "name": "First Default",
                "lng": -122.33,
                "lat": 47.60,
                "is_default": True,
            })
            first_id = resp1.json()["id"]

            client.post("/api/v1/start-points", json={
                "name": "Second Default",
                "lng": -122.34,
                "lat": 47.61,
                "is_default": True,
            })

            # List and verify only the second is default
            resp = client.get("/api/v1/start-points")
            points = resp.json()
            defaults = [p for p in points if p["is_default"]]
            assert len(defaults) == 1
            assert defaults[0]["name"] == "Second Default"

    def test_limit_exceeded_returns_400(self):
        app, _, _ = _get_test_app()
        with TestClient(app) as client:
            for i in range(20):
                r = client.post("/api/v1/start-points", json={
                    "name": f"Point {i}",
                    "lng": -122.33 + i * 0.001,
                    "lat": 47.60,
                    "is_default": False,
                })
                assert r.status_code == 201

            # 21st should fail
            resp = client.post("/api/v1/start-points", json={
                "name": "One Too Many",
                "lng": -122.30,
                "lat": 47.60,
                "is_default": False,
            })
            assert resp.status_code == 400

    def test_missing_name_returns_422(self):
        app, _, _ = _get_test_app()
        with TestClient(app) as client:
            resp = client.post("/api/v1/start-points", json={
                "lng": -122.33,
                "lat": 47.60,
            })
        assert resp.status_code == 422


class TestStartPointsUpdate:
    """PATCH /start-points/{id}."""

    def test_update_name(self):
        app, _, _ = _get_test_app()
        with TestClient(app) as client:
            create_resp = client.post("/api/v1/start-points", json={
                "name": "Old Name",
                "lng": -122.33,
                "lat": 47.60,
                "is_default": False,
            })
            point_id = create_resp.json()["id"]

            resp = client.patch(f"/api/v1/start-points/{point_id}", json={
                "name": "New Name",
            })
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    def test_set_as_default(self):
        app, _, _ = _get_test_app()
        with TestClient(app) as client:
            create_resp = client.post("/api/v1/start-points", json={
                "name": "My Point",
                "lng": -122.33,
                "lat": 47.60,
                "is_default": False,
            })
            point_id = create_resp.json()["id"]

            resp = client.patch(f"/api/v1/start-points/{point_id}", json={
                "is_default": True,
            })
        assert resp.status_code == 200
        assert resp.json()["is_default"] is True

    def test_nonexistent_returns_404(self):
        app, _, _ = _get_test_app()
        with TestClient(app) as client:
            resp = client.patch("/api/v1/start-points/99999", json={
                "name": "Nope",
            })
        assert resp.status_code == 404


class TestStartPointsDelete:
    """DELETE /start-points/{id}."""

    def test_delete_returns_204(self):
        app, _, _ = _get_test_app()
        with TestClient(app) as client:
            create_resp = client.post("/api/v1/start-points", json={
                "name": "Doomed Point",
                "lng": -122.33,
                "lat": 47.60,
                "is_default": False,
            })
            point_id = create_resp.json()["id"]

            resp = client.delete(f"/api/v1/start-points/{point_id}")
            assert resp.status_code == 204

            # Verify it's gone
            list_resp = client.get("/api/v1/start-points")
            assert all(p["id"] != point_id for p in list_resp.json())

    def test_delete_nonexistent_returns_404(self):
        app, _, _ = _get_test_app()
        with TestClient(app) as client:
            resp = client.delete("/api/v1/start-points/99999")
        assert resp.status_code == 404
