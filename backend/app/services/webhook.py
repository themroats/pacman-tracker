"""
Strava webhook event handler.

Dispatches activity create/update/delete events and triggers incremental sync.
"""

from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.models.user import User
from app.services.crypto import decrypt_token


async def handle_webhook_event(
    db: Session,
    aspect_type: str,
    strava_activity_id: int,
    strava_athlete_id: int,
) -> None:
    """
    Handle a Strava webhook event.

    Args:
        db: Database session
        aspect_type: "create", "update", or "delete"
        strava_activity_id: Strava activity ID
        strava_athlete_id: Strava athlete ID (owner)
    """
    # Find the user by Strava athlete ID
    user = db.query(User).filter_by(strava_athlete_id=strava_athlete_id).first()
    if not user:
        # Unknown athlete — ignore
        return

    if aspect_type == "delete":
        # Remove local activity record
        activity = (
            db.query(Activity)
            .filter_by(strava_activity_id=strava_activity_id, user_id=user.id)
            .first()
        )
        if activity:
            db.delete(activity)
            db.flush()
        return

    if aspect_type in ("create", "update"):
        # Trigger incremental import for this specific activity
        from app.services.importer import ActivityImporter

        try:
            access_token = decrypt_token(user.access_token_encrypted)
            importer = ActivityImporter(db_session=db)

            # Check if activity already exists
            existing = (
                db.query(Activity)
                .filter_by(strava_activity_id=strava_activity_id)
                .first()
            )

            if existing and aspect_type == "update":
                # Re-fetch the activity detail to update
                detail = await importer.strava.fetch_activity_detail(
                    access_token, strava_activity_id
                )
                existing.name = detail.get("name", existing.name)
                existing.distance_meters = detail.get("distance", existing.distance_meters)
                existing.duration_seconds = detail.get("elapsed_time", existing.duration_seconds)
                existing.moving_time_seconds = detail.get("moving_time", existing.moving_time_seconds)
                db.flush()
            elif not existing and aspect_type == "create":
                # Import the single new activity
                await importer.import_phase_a(
                    user_id=user.id, access_token=access_token
                )
        except Exception:
            # Log error but don't fail the webhook response
            pass
