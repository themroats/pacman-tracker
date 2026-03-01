"""
Auth API router — Strava OAuth endpoints.

Endpoints:
- GET  /auth/strava          → Redirect to Strava login
- GET  /auth/strava/callback  → Handle OAuth callback
- POST /auth/logout           → End user session
"""

import datetime

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import AppError
from app.models.user import User
from app.schemas.user import AuthCallbackResponse, LogoutResponse
from app.services.crypto import encrypt_token
from app.services.strava import StravaOAuthService

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory state store for CSRF tokens (use Redis in production)
_csrf_states: dict[str, datetime.datetime] = {}


@router.get("/strava")
async def strava_login():
    """Redirect user to Strava OAuth authorization page."""
    service = StravaOAuthService()
    url, state = service.get_authorization_url()
    _csrf_states[state] = datetime.datetime.now(datetime.UTC)
    return RedirectResponse(url=url, status_code=302)


@router.get("/strava/callback", response_model=AuthCallbackResponse)
async def strava_callback(
    code: str = Query(...),
    scope: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """Handle Strava OAuth callback after user authorization."""
    # Validate CSRF state
    if state not in _csrf_states:
        raise AppError("VALIDATION_ERROR", "Invalid state parameter", 400)

    # Clean up used state
    del _csrf_states[state]

    # Exchange code for tokens
    service = StravaOAuthService()
    try:
        token_data = await service.exchange_code(code)
    except Exception as e:
        raise AppError("STRAVA_UNAVAILABLE", f"Failed to exchange code: {e}", 503)

    # Find or create user
    user = (
        db.query(User)
        .filter_by(strava_athlete_id=token_data["athlete_id"])
        .first()
    )

    if user is None:
        user = User(
            strava_athlete_id=token_data["athlete_id"],
            display_name=token_data["display_name"],
            profile_image_url=token_data.get("profile_image_url"),
            access_token_encrypted=encrypt_token(token_data["access_token"]),
            refresh_token_encrypted=encrypt_token(token_data["refresh_token"]),
            token_expires_at=token_data["expires_at"],
            strava_scope=scope,
            sync_status="importing",
        )
        db.add(user)
        db.flush()
    else:
        # Update tokens
        user.access_token_encrypted = encrypt_token(token_data["access_token"])
        user.refresh_token_encrypted = encrypt_token(token_data["refresh_token"])
        user.token_expires_at = token_data["expires_at"]
        user.strava_scope = scope
        user.display_name = token_data["display_name"]
        user.profile_image_url = token_data.get("profile_image_url")
        if user.sync_status == "revoked":
            user.sync_status = "importing"

    return AuthCallbackResponse(
        user_id=user.id,
        display_name=user.display_name,
        access_token=token_data["access_token"],
        home_city=user.home_city_id,
        sync_status=user.sync_status,
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout():
    """End user session."""
    return LogoutResponse(message="Logged out")
