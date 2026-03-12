"""
Unit tests for the Strava webhook event handler.

Tests:
- Delete event removes activity
- Create event triggers import
- Update event refreshes activity details
- Unknown athlete is ignored
- Non-activity events are ignored (handled by router, not handler)
"""

import datetime

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.activity import Activity
from app.models.user import User
from app.services.webhook import handle_webhook_event


@pytest.fixture()
def user_in_db(db_session):
    """Create a user in the test DB."""
    from app.database import Base
    Base.metadata.create_all(db_session.get_bind())

    user = User(
        strava_athlete_id=99999,
        display_name="Webhook Tester",
        access_token_encrypted="encrypted_tok",
        refresh_token_encrypted="encrypted_rtok",
        token_expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=6),
        strava_scope="activity:read_all",
        sync_status="idle",
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture()
def activity_in_db(db_session, user_in_db):
    """Create an activity belonging to the test user."""
    activity = Activity(
        user_id=user_in_db.id,
        strava_activity_id=12345678,
        name="Morning Run",
        sport_type="Run",
        distance_meters=5000,
        duration_seconds=1800,
        moving_time_seconds=1700,
        start_date=datetime.datetime(2025, 6, 1, 8, 0, tzinfo=datetime.UTC),
    )
    db_session.add(activity)
    db_session.flush()
    return activity


class TestDeleteEvent:
    """Webhook delete events should remove the activity."""

    @pytest.mark.asyncio
    async def test_deletes_existing_activity(self, db_session, user_in_db, activity_in_db):
        assert db_session.query(Activity).count() == 1

        await handle_webhook_event(
            db=db_session,
            aspect_type="delete",
            strava_activity_id=12345678,
            strava_athlete_id=99999,
        )

        assert db_session.query(Activity).count() == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent_activity_is_noop(self, db_session, user_in_db):
        await handle_webhook_event(
            db=db_session,
            aspect_type="delete",
            strava_activity_id=99999999,
            strava_athlete_id=99999,
        )
        # Should not raise


class TestCreateEvent:
    """Webhook create events should trigger activity import."""

    @pytest.mark.asyncio
    @patch("app.services.webhook.decrypt_token", return_value="fake_access_token")
    @patch("app.services.importer.ActivityImporter")
    async def test_create_triggers_import(self, MockImporter, mock_decrypt, db_session, user_in_db):
        mock_instance = MockImporter.return_value
        mock_instance.import_phase_a = AsyncMock()

        with patch("app.services.webhook.ActivityImporter", MockImporter, create=True):
            await handle_webhook_event(
                db=db_session,
                aspect_type="create",
                strava_activity_id=55555555,
                strava_athlete_id=99999,
            )

        mock_decrypt.assert_called_once_with("encrypted_tok")
        mock_instance.import_phase_a.assert_called_once_with(
            user_id=user_in_db.id, access_token="fake_access_token"
        )


class TestUpdateEvent:
    """Webhook update events should refresh activity details."""

    @pytest.mark.asyncio
    @patch("app.services.webhook.decrypt_token", return_value="fake_access_token")
    @patch("app.services.importer.ActivityImporter")
    async def test_update_refreshes_existing(self, MockImporter, mock_decrypt, db_session, user_in_db, activity_in_db):
        mock_instance = MockImporter.return_value
        mock_instance.strava = MagicMock()
        mock_instance.strava.fetch_activity_detail = AsyncMock(return_value={
            "name": "Updated Run",
            "distance": 5500,
            "elapsed_time": 2000,
            "moving_time": 1900,
        })

        with patch("app.services.webhook.ActivityImporter", MockImporter, create=True):
            await handle_webhook_event(
                db=db_session,
                aspect_type="update",
                strava_activity_id=12345678,
                strava_athlete_id=99999,
            )

        activity = db_session.query(Activity).first()
        assert activity.name == "Updated Run"
        assert activity.distance_meters == 5500


class TestUnknownAthlete:
    """Events from unknown athletes should be silently ignored."""

    @pytest.mark.asyncio
    async def test_unknown_athlete_is_noop(self, db_session, user_in_db):
        await handle_webhook_event(
            db=db_session,
            aspect_type="create",
            strava_activity_id=11111111,
            strava_athlete_id=00000,  # not in DB
        )
        # Should not raise or create anything
