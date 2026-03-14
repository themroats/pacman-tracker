"""In-process tracking for background sync jobs and stale-status recovery."""

import logging

from sqlalchemy.orm import Session

from app.models.user import User

logger = logging.getLogger(__name__)

_active_sync_jobs: set[int] = set()


def mark_sync_started(user_id: int) -> None:
    """Record that this process started a sync-related background job for a user."""
    _active_sync_jobs.add(user_id)


def mark_sync_finished(user_id: int) -> None:
    """Record that this process no longer has a sync-related job for a user."""
    _active_sync_jobs.discard(user_id)


def has_active_sync(user_id: int) -> bool:
    """Return whether this process is actively running a sync-related job for a user."""
    return user_id in _active_sync_jobs


def clear_active_sync_jobs() -> None:
    """Clear runtime tracking state. Intended for tests."""
    _active_sync_jobs.clear()


def recover_stale_sync_status(db: Session, user: User) -> str | None:
    """Recover a persisted busy status when no in-process job exists after a restart.

    Returns a user-facing message when a stale status was recovered, else None.
    """
    if user.sync_status not in {"importing", "syncing"}:
        return None

    if has_active_sync(user.id):
        return None

    logger.warning(
        "Recovering stale sync status for user %d from %s to error",
        user.id,
        user.sync_status,
    )
    user.sync_status = "error"
    db.commit()
    return "Previous sync was interrupted by an app restart. Please run it again."