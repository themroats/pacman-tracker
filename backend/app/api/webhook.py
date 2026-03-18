"""
Strava webhook API router.

Endpoints:
- GET  /webhook/strava → Subscription verification 
- POST /webhook/strava → Event receiver
"""

import logging

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.main import AppError
from app.services.strava import TokenRevokedError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.get("/strava")
async def strava_webhook_verify(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
):
    """
    Strava webhook subscription verification.

    Called by Strava during subscription setup. Echoes back the challenge
    if the verify_token matches.
    """
    settings = get_settings()
    if hub_verify_token != settings.strava_webhook_verify_token:
        raise AppError("VALIDATION_ERROR", "Invalid verify token", 403)

    return {"hub.challenge": hub_challenge}


@router.post("/strava")
async def strava_webhook_event(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Receive Strava push event notifications.

    Dispatches create/update/delete events to the webhook handler service.
    """
    body = await request.json()

    aspect_type = body.get("aspect_type")
    object_id = body.get("object_id")
    object_type = body.get("object_type")
    owner_id = body.get("owner_id")

    if object_type != "activity":
        return {"status": "ignored"}

    # Dispatch to webhook handler
    from app.services.webhook import handle_webhook_event

    try:
        await handle_webhook_event(
            db=db,
            aspect_type=aspect_type,
            strava_activity_id=object_id,
            strava_athlete_id=owner_id,
        )
    except TokenRevokedError:
        # Token revocation is non-retryable — acknowledge the webhook
        logger.warning("Token revoked for athlete %s during webhook processing", owner_id)
        return {"status": "received"}
    except Exception:
        logger.exception("Webhook processing failed for athlete %s, activity %s", owner_id, object_id)
        raise  # Returns 500 so Strava retries

    return {"status": "received"}
