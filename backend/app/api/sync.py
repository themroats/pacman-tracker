"""
Sync API router — sync status and trigger endpoints.

Endpoints:
- GET  /sync/status  → Current sync status
- POST /sync/trigger → Trigger incremental sync
"""

import asyncio
import datetime
import logging

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import AppError
from app.models.activity import Activity
from app.models.user import User
from app.schemas.user import SyncStatusResponse
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("/status", response_model=SyncStatusResponse)
async def sync_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get current sync status for the authenticated user."""
    total = db.query(Activity).filter_by(user_id=user.id).count()
    imported = (
        db.query(Activity)
        .filter(
            Activity.user_id == user.id,
            Activity.import_status.in_(["polyline_imported", "streams_imported", "matched"]),
        )
        .count()
    )
    matched = (
        db.query(Activity)
        .filter_by(user_id=user.id, import_status="matched")
        .count()
    )

    return SyncStatusResponse(
        status=user.sync_status,
        total_activities=total,
        imported_activities=imported,
        matched_activities=matched,
        last_sync_at=user.last_sync_at,
    )


@router.post("/trigger")
async def trigger_sync(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Manually trigger an incremental sync of new Strava activities."""
    if user.sync_status in ("importing", "syncing"):
        raise AppError("VALIDATION_ERROR", "Sync already in progress", 400)

    if user.sync_status == "revoked":
        raise AppError("UNAUTHORIZED", "Strava connection is revoked. Please reconnect.", 401)

    user.sync_status = "syncing"
    db.commit()

    from app.services.crypto import decrypt_token

    access_token = decrypt_token(user.access_token_encrypted)
    asyncio.create_task(_run_background_sync(user.id, access_token))

    return {"message": "Sync started", "status": user.sync_status}


async def _run_background_sync(user_id: int, access_token: str):
    """Run incremental sync in the background with its own DB session.

    Uses a dedicated session so that status updates (including "error")
    are committed independently from the request lifecycle — fixing the
    rollback bug where ``get_db()`` would undo the ``sync_status="error"``
    update when an exception propagated through the dependency.
    """
    from app.database import get_session_factory
    from app.services.importer import ActivityImporter

    logger.info("Starting background sync for user %d", user_id)
    factory = get_session_factory()
    session = factory()

    try:
        importer = ActivityImporter(db_session=session)
        result = await importer.import_phase_a(user_id=user_id, access_token=access_token)

        user = session.get(User, user_id)
        if user:
            user.sync_status = "idle"
            user.last_sync_at = datetime.datetime.now(datetime.UTC)

        session.commit()
        logger.info(
            "Sync finished for user %d — %d activities imported",
            user_id,
            result.get("imported", 0),
        )
    except Exception:
        logger.exception("Background sync failed for user %d", user_id)
        session.rollback()
        try:
            user = session.get(User, user_id)
            if user:
                user.sync_status = "error"
                session.commit()
        except Exception:
            session.rollback()
    finally:
        session.close()
