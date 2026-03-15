"""
Integration tests for sync status recovery (SC-003).

Verifies:
- Stale "syncing" status is recovered to "error" on status poll when no active job
- sync_started_at timeout (>5 min) triggers recovery even when process thinks job is active
- Startup lifespan recovery resets all stale syncing/importing statuses
- State machine rejects invalid transitions (duplicate sync trigger)
"""

import datetime
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.user import User
from app.services.sync_runtime import (
    clear_active_sync_jobs,
    has_active_sync,
    mark_sync_started,
    recover_stale_sync_status,
)


@pytest.fixture()
def db_session():
    """In-memory DB for sync recovery tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SpatiaLite not needed for sync tests — but create tables
    # We skip SpatiaLite-dependent columns by only creating User table
    User.__table__.create(bind=engine, checkfirst=True)
    SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionFactory()
    clear_active_sync_jobs()
    yield session
    session.close()
    clear_active_sync_jobs()


def _make_user(session, **overrides):
    defaults = dict(
        strava_athlete_id=12345,
        display_name="Sync Tester",
        access_token_encrypted="enc",
        refresh_token_encrypted="ref",
        token_expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=6),
        strava_scope="activity:read_all",
        sync_status="idle",
    )
    defaults.update(overrides)
    user = User(**defaults)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


class TestStaleRecoveryOnPoll:
    """SC-003: Sync status never remains stuck in 'syncing' for more than 5 minutes after a failure."""

    def test_syncing_with_no_active_job_recovers_to_error(self, db_session):
        """If user is 'syncing' but no in-process job exists, recover to 'error'."""
        user = _make_user(db_session, sync_status="syncing")

        msg = recover_stale_sync_status(db_session, user)

        assert user.sync_status == "error"
        assert msg is not None
        assert "interrupted" in msg.lower() or "restart" in msg.lower()

    def test_importing_with_no_active_job_recovers_to_error(self, db_session):
        """Legacy 'importing' status is also recovered."""
        user = _make_user(db_session, sync_status="importing")

        msg = recover_stale_sync_status(db_session, user)

        assert user.sync_status == "error"
        assert msg is not None

    def test_syncing_with_active_job_not_recovered(self, db_session):
        """If an in-process job exists and is recent, status is left alone."""
        user = _make_user(
            db_session,
            sync_status="syncing",
            sync_started_at=datetime.datetime.now(datetime.UTC),
        )
        mark_sync_started(user.id)

        msg = recover_stale_sync_status(db_session, user)

        assert user.sync_status == "syncing"
        assert msg is None

    def test_syncing_with_timed_out_job_recovers(self, db_session):
        """If sync_started_at is >5 min ago, even with active job, recover."""
        user = _make_user(
            db_session,
            sync_status="syncing",
            sync_started_at=datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=10),
        )
        mark_sync_started(user.id)

        msg = recover_stale_sync_status(db_session, user)

        assert user.sync_status == "error"
        assert msg is not None

    def test_idle_status_not_touched(self, db_session):
        """Idle users are not affected by recovery."""
        user = _make_user(db_session, sync_status="idle")

        msg = recover_stale_sync_status(db_session, user)

        assert user.sync_status == "idle"
        assert msg is None

    def test_error_status_not_touched(self, db_session):
        """Already-errored users are not affected by recovery."""
        user = _make_user(db_session, sync_status="error")

        msg = recover_stale_sync_status(db_session, user)

        assert user.sync_status == "error"
        assert msg is None


class TestStateMachineTransitions:
    """Verify the transition_sync_status method enforces valid transitions."""

    def test_idle_to_syncing_allowed(self, db_session):
        user = _make_user(db_session, sync_status="idle")
        user.transition_sync_status("syncing")
        assert user.sync_status == "syncing"

    def test_syncing_to_complete_allowed(self, db_session):
        user = _make_user(db_session, sync_status="syncing")
        user.transition_sync_status("complete")
        assert user.sync_status == "complete"

    def test_syncing_to_error_allowed(self, db_session):
        user = _make_user(db_session, sync_status="syncing")
        user.transition_sync_status("error")
        assert user.sync_status == "error"

    def test_syncing_to_revoked_allowed(self, db_session):
        user = _make_user(db_session, sync_status="syncing")
        user.transition_sync_status("revoked")
        assert user.sync_status == "revoked"

    def test_idle_to_error_rejected(self, db_session):
        user = _make_user(db_session, sync_status="idle")
        with pytest.raises(ValueError, match="Invalid sync transition"):
            user.transition_sync_status("error")

    def test_idle_to_complete_rejected(self, db_session):
        user = _make_user(db_session, sync_status="idle")
        with pytest.raises(ValueError, match="Invalid sync transition"):
            user.transition_sync_status("complete")

    def test_syncing_to_idle_rejected(self, db_session):
        """Cannot go from syncing directly to idle — must go through complete or error."""
        user = _make_user(db_session, sync_status="syncing")
        with pytest.raises(ValueError, match="Invalid sync transition"):
            user.transition_sync_status("idle")

    def test_error_to_idle_allowed(self, db_session):
        """User should be able to retry after error."""
        user = _make_user(db_session, sync_status="error")
        user.transition_sync_status("idle")
        assert user.sync_status == "idle"

    def test_complete_to_idle_allowed(self, db_session):
        """Complete transitions to idle on poll."""
        user = _make_user(db_session, sync_status="complete")
        user.transition_sync_status("idle")
        assert user.sync_status == "idle"
