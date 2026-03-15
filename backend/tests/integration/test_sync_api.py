"""Integration tests for sync endpoints."""

import datetime
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import MagicMock

from app.database import get_db
from app.models.user import User
from app.services.sync_runtime import clear_active_sync_jobs, mark_sync_finished, mark_sync_started


@asynccontextmanager
async def _noop_lifespan(app):
    yield


def _create_app():
    with patch("app.main.lifespan", _noop_lifespan):
        from app.main import create_app

        return create_app()


def _make_test_session():
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    User.__table__.create(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def test_trigger_coverage_starts_background_matcher():
    app = _create_app()
    from app.api import sync as sync_api

    clear_active_sync_jobs()

    SessionFactory = _make_test_session()
    session = SessionFactory()

    user = User(
        strava_athlete_id=12345,
        display_name="Coverage Runner",
        profile_image_url=None,
        access_token_encrypted="encrypted-access",
        refresh_token_encrypted="encrypted-refresh",
        token_expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1),
        strava_scope="activity:read_all",
        sync_status="idle",
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    def override_get_db():
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[sync_api.get_current_user] = lambda: user

    def fake_create_task(coro):
        coro.close()
        return object()

    with patch(
        "app.services.crypto.decrypt_token",
        return_value="access-token",
    ), patch("app.api.sync._run_background_coverage", new=AsyncMock(return_value=None)), patch(
        "app.api.sync.asyncio.create_task",
        side_effect=fake_create_task,
    ) as create_task:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/sync/coverage",
                headers={"Authorization": "Bearer access-token"},
            )

    assert response.status_code == 200
    assert response.json() == {
        "message": "Coverage matching started",
        "status": "syncing",
    }
    create_task.assert_called_once()
    session.close()


def test_trigger_coverage_rejects_when_sync_in_progress():
    app = _create_app()
    from app.api import sync as sync_api

    clear_active_sync_jobs()

    SessionFactory = _make_test_session()
    session = SessionFactory()

    user = User(
        strava_athlete_id=12346,
        display_name="Busy Runner",
        profile_image_url=None,
        access_token_encrypted="encrypted-access",
        refresh_token_encrypted="encrypted-refresh",
        token_expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1),
        strava_scope="activity:read_all",
        sync_status="syncing",
    )
    session.add(user)
    session.commit()

    def override_get_db():
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[sync_api.get_current_user] = lambda: user

    mark_sync_started(user.id)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/sync/coverage",
                headers={"Authorization": "Bearer access-token"},
            )
    finally:
        mark_sync_finished(user.id)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    session.close()


def test_sync_status_recovers_stale_busy_state_after_restart():
    app = _create_app()
    from app.api import sync as sync_api

    clear_active_sync_jobs()

    SessionFactory = _make_test_session()
    session = SessionFactory()

    user = User(
        strava_athlete_id=12347,
        display_name="Recovered Runner",
        profile_image_url=None,
        access_token_encrypted="encrypted-access",
        refresh_token_encrypted="encrypted-refresh",
        token_expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1),
        strava_scope="activity:read_all",
        sync_status="syncing",
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    def override_get_db():
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[sync_api.get_current_user] = lambda: user

    activity_query = MagicMock()
    activity_query.filter_by.return_value.count.return_value = 0
    activity_query.filter.return_value.count.return_value = 0
    session.query = MagicMock(return_value=activity_query)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/sync/status",
            headers={"Authorization": "Bearer access-token"},
        )

    session.refresh(user)
    assert response.status_code == 200
    assert response.json()["status"] == "error"
    assert response.json()["error_message"] == "Previous sync was interrupted by an app restart. Please run it again."
    assert user.sync_status == "error"
    session.close()


def test_trigger_coverage_recovers_stale_busy_state_before_restart():
    app = _create_app()
    from app.api import sync as sync_api

    clear_active_sync_jobs()

    SessionFactory = _make_test_session()
    session = SessionFactory()

    user = User(
        strava_athlete_id=12348,
        display_name="Retry Runner",
        profile_image_url=None,
        access_token_encrypted="encrypted-access",
        refresh_token_encrypted="encrypted-refresh",
        token_expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1),
        strava_scope="activity:read_all",
        sync_status="syncing",
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    def override_get_db():
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[sync_api.get_current_user] = lambda: user

    def fake_create_task(coro):
        coro.close()
        return object()

    with patch(
        "app.services.crypto.decrypt_token",
        return_value="access-token",
    ), patch("app.api.sync._run_background_coverage", new=AsyncMock(return_value=None)), patch(
        "app.api.sync.asyncio.create_task",
        side_effect=fake_create_task,
    ) as create_task:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/sync/coverage",
                headers={"Authorization": "Bearer access-token"},
            )

    session.refresh(user)
    assert response.status_code == 200
    assert response.json() == {
        "message": "Coverage matching started",
        "status": "syncing",
    }
    create_task.assert_called_once()
    assert user.sync_status == "syncing"
    session.close()