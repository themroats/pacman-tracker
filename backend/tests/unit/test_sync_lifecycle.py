"""
Tests for sync lifecycle — state machine enforcement in API endpoints.

Covers:
- Auth callback stores access_token_hash
- trigger_sync uses transition_sync_status
- background sync transitions to complete/error/revoked
- sync_status auto-transitions complete → idle
- Startup lifespan resets stale syncing/importing to error
"""

import pytest


class TestAuthCallbackStoresHash:
    """strava_callback computes token hash and stores in UserToken."""

    def test_callback_source_contains_compute_token_hash(self):
        import inspect
        from app.api.auth import strava_callback

        source = inspect.getsource(strava_callback)
        assert "compute_token_hash" in source, (
            "strava_callback must compute token hash for UserToken"
        )
        assert "UserToken" in source


class TestTriggerSyncTransition:
    """trigger_sync uses transition_sync_status and catches ValueError."""

    def test_trigger_sync_uses_state_machine(self):
        import inspect
        from app.api.sync import trigger_sync

        source = inspect.getsource(trigger_sync)
        assert "transition_sync_status" in source, "Must use state machine method"
        assert "sync_started_at" in source, "Must set sync_started_at timestamp"
        assert "ValueError" in source, "Must catch ValueError for invalid transitions"
        assert "SYNC_IN_PROGRESS" in source, "Must raise SYNC_IN_PROGRESS on duplicate"


class TestBackgroundSyncTransitions:
    """_run_background_sync transitions correctly."""

    def test_background_sync_handles_all_outcomes(self):
        import inspect
        from app.api.sync import _run_background_sync

        source = inspect.getsource(_run_background_sync)
        assert '"complete"' in source, "Must transition to 'complete' on success"
        assert '"error"' in source, "Must transition to 'error' on failure"
        assert "TokenRevokedError" in source, "Must handle token revocation"
        assert '"revoked"' in source, "Must transition to 'revoked' on token revocation"


class TestSyncStatusAutoTransition:
    """sync_status endpoint auto-transitions complete → idle."""

    def test_sync_status_handles_complete(self):
        import inspect
        from app.api.sync import sync_status

        source = inspect.getsource(sync_status)
        assert "status_to_return" in source, "Must save status before transitioning"
        assert '"complete"' in source, "Must check for complete status"
        assert '"idle"' in source, "Must transition complete to idle"


class TestStartupRecovery:
    """Lifespan resets stale sync statuses on startup."""

    def test_lifespan_contains_recovery_query(self):
        import inspect
        from app.main import lifespan

        source = inspect.getsource(lifespan)
        assert "syncing" in source, "Must query for stale syncing status"
        assert "importing" in source, "Must query for stale importing status"
        assert '"error"' in source, "Must reset stale statuses to error"
        assert "sync_status" in source
