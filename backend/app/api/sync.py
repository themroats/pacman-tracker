"""
Sync API router — sync status and trigger endpoints.

Endpoints:
- GET  /sync/status  → Current sync status
- POST /sync/trigger → Trigger incremental sync
"""

import datetime

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import AppError
from app.models.activity import Activity
from app.models.user import User
from app.schemas.user import SyncStatusResponse

router = APIRouter(prefix="/sync", tags=["sync"])


def get_current_user(
    db: Session = Depends(get_db),
    authorization: str = Header(None),
) -> User:
    """Extract user from auth header. Placeholder — will be enhanced with proper session management."""
    if not authorization:
        raise AppError("UNAUTHORIZED", "Missing authorization header", 401)
    # In a full implementation, decode the JWT/session token
    # For now, extract user_id from a simple bearer token scheme
    # This will be replaced with proper auth middleware
    raise AppError("UNAUTHORIZED", "Auth not fully implemented", 401)


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
    db.flush()

    # In production, this would dispatch to a background task
    # For now, run inline
    from app.services.crypto import decrypt_token
    from app.services.importer import ActivityImporter

    access_token = decrypt_token(user.access_token_encrypted)
    importer = ActivityImporter(db_session=db)

    try:
        result = await importer.import_phase_a(user_id=user.id, access_token=access_token)
        user.sync_status = "idle"
        user.last_sync_at = datetime.datetime.now(datetime.UTC)
    except Exception as e:
        user.sync_status = "error"
        raise AppError("INTERNAL_ERROR", f"Sync failed: {e}", 500)

    return {"message": "Sync started", "status": user.sync_status}
