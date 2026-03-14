"""Integration tests for manual bootstrap admin endpoints."""

import os
from contextlib import asynccontextmanager
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.services.city_bootstrap import reset_city_bootstrap_state
from app.services.neighborhood_bootstrap import reset_neighborhood_bootstrap_state


@asynccontextmanager
async def _noop_lifespan(app):
    yield


def _create_app():
    with patch("app.main.lifespan", _noop_lifespan):
        from app.main import create_app

        return create_app()


def test_bootstrap_status_requires_token():
    reset_city_bootstrap_state()
    reset_neighborhood_bootstrap_state()
    with patch.dict(os.environ, {"MANUAL_BOOTSTRAP_TOKEN": "bootstrap-secret"}, clear=False):
        app = _create_app()
        with TestClient(app) as client:
            response = client.get("/api/v1/admin/bootstrap/cities")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_bootstrap_status_returns_state_when_authorized():
    reset_city_bootstrap_state()
    reset_neighborhood_bootstrap_state()
    with patch.dict(os.environ, {"MANUAL_BOOTSTRAP_TOKEN": "bootstrap-secret"}, clear=False), patch(
        "app.api.admin.get_city_bootstrap_state",
        return_value={"status": "idle", "in_progress": False, "error": None},
    ):
        app = _create_app()
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/admin/bootstrap/cities",
                headers={"X-Admin-Token": "bootstrap-secret"},
            )

    assert response.status_code == 200
    assert response.json() == {"status": "idle", "in_progress": False, "error": None}


def test_trigger_city_bootstrap_starts_background_load():
    reset_city_bootstrap_state()
    reset_neighborhood_bootstrap_state()
    with patch.dict(os.environ, {"MANUAL_BOOTSTRAP_TOKEN": "bootstrap-secret"}, clear=False), patch(
        "app.api.admin.start_city_bootstrap",
        return_value={"status": "loading", "in_progress": True, "error": None},
    ) as start_bootstrap:
        app = _create_app()
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/admin/bootstrap/cities",
                params={"city": "Seattle"},
                headers={"X-Admin-Token": "bootstrap-secret"},
            )

    assert response.status_code == 202
    assert response.json() == {"status": "loading", "in_progress": True, "error": None}
    start_bootstrap.assert_called_once_with("Seattle")


def test_neighborhood_bootstrap_status_returns_state_when_authorized():
    reset_city_bootstrap_state()
    reset_neighborhood_bootstrap_state()
    with patch.dict(os.environ, {"MANUAL_BOOTSTRAP_TOKEN": "bootstrap-secret"}, clear=False), patch(
        "app.api.admin.get_neighborhood_bootstrap_state",
        return_value={
            "status": "idle",
            "in_progress": False,
            "error": None,
            "city": "Seattle",
            "loaded": 0,
            "total": 12,
            "processed": 3,
            "assigned": 240,
            "unassigned": 12,
        },
    ) as get_state:
        app = _create_app()
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/admin/bootstrap/neighborhoods",
                params={"city": "Seattle"},
                headers={"X-Admin-Token": "bootstrap-secret"},
            )

    assert response.status_code == 200
    assert response.json() == {
        "status": "idle",
        "in_progress": False,
        "error": None,
        "city": "Seattle",
        "loaded": 0,
        "total": 12,
        "processed": 3,
        "assigned": 240,
        "unassigned": 12,
    }
    get_state.assert_called_once_with("Seattle")


def test_trigger_neighborhood_bootstrap_starts_background_load():
    reset_city_bootstrap_state()
    reset_neighborhood_bootstrap_state()
    with patch.dict(os.environ, {"MANUAL_BOOTSTRAP_TOKEN": "bootstrap-secret"}, clear=False), patch(
        "app.api.admin.start_neighborhood_bootstrap",
        return_value={
            "status": "loading",
            "in_progress": True,
            "error": None,
            "city": "Seattle",
            "loaded": 0,
            "total": 12,
            "processed": 0,
            "assigned": 0,
            "unassigned": 0,
        },
    ) as start_bootstrap:
        app = _create_app()
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/admin/bootstrap/neighborhoods",
                params={"city": "Seattle"},
                headers={"X-Admin-Token": "bootstrap-secret"},
            )

    assert response.status_code == 202
    assert response.json() == {
        "status": "loading",
        "in_progress": True,
        "error": None,
        "city": "Seattle",
        "loaded": 0,
        "total": 12,
        "processed": 0,
        "assigned": 0,
        "unassigned": 0,
    }
    start_bootstrap.assert_called_once_with("Seattle")