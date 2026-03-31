"""
Auth API router — Strava OAuth endpoints.

Endpoints:
- GET  /auth/strava          → Redirect to Strava login
- GET  /auth/strava/callback  → Handle OAuth callback
- POST /auth/logout           → End user session
"""

import base64
import datetime
import hashlib
import hmac
import json
import logging
import time

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.errors import AppError
from app.models.user import User
from app.models.user_token import UserToken
from app.schemas.user import AuthCallbackResponse, LogoutResponse
from app.services.crypto import compute_token_hash, encrypt_token
from app.services.strava import StravaAPIError, StravaOAuthService, TokenRevokedError
from app.services.sync_runtime import mark_sync_finished, mark_sync_started

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(raw + padding)


def _issue_state_token() -> str:
    """Create a signed OAuth state token that survives restarts and scale-out."""
    settings = get_settings()
    payload = {
        "nonce": hashlib.sha256(f"{time.time_ns()}".encode("utf-8")).hexdigest(),
        "ts": int(time.time()),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(
        settings.secret_key.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).digest()
    return f"{_b64url_encode(payload_bytes)}.{_b64url_encode(signature)}"


def _validate_state_token(token: str, max_age_seconds: int = 900) -> bool:
    """Validate the signed OAuth state token and reject expired or tampered values."""
    try:
        payload_part, signature_part = token.split(".", 1)
        payload_bytes = _b64url_decode(payload_part)
        signature = _b64url_decode(signature_part)
        settings = get_settings()
        expected_signature = hmac.new(
            settings.secret_key.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(signature, expected_signature):
            return False

        payload = json.loads(payload_bytes.decode("utf-8"))
        issued_at = int(payload["ts"])
        return (int(time.time()) - issued_at) <= max_age_seconds
    except Exception:
        return False


@router.get("/strava")
def strava_login():
    """Redirect user to Strava OAuth authorization page."""
    service = StravaOAuthService()
    state = _issue_state_token()
    url, _ = service.get_authorization_url(state=state)
    return RedirectResponse(url=url, status_code=302)


@router.get("/strava/callback", response_model=AuthCallbackResponse)
async def strava_callback(
    code: str = Query(...),
    scope: str = Query(...),
    state: str = Query(...),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """Handle Strava OAuth callback after user authorization."""
    # Validate CSRF state
    if not _validate_state_token(state):
        raise AppError("VALIDATION_ERROR", "Invalid state parameter", 400)

    # Exchange code for tokens
    service = StravaOAuthService()
    try:
        token_data = await service.exchange_code(code)
    except StravaAPIError as e:
        raise AppError("STRAVA_UNAVAILABLE", f"Failed to exchange code: {e.message}", 503)
    except TokenRevokedError as e:
        raise AppError("STRAVA_UNAVAILABLE", f"Failed to exchange code: {e}", 503)
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

    # Upsert a UserToken row for this frontend session
    new_hash = compute_token_hash(token_data["access_token"])
    existing_token = db.query(UserToken).filter_by(token_hash=new_hash).first()
    if not existing_token:
        # Remove old frontend tokens for this user (one active frontend session)
        db.query(UserToken).filter_by(user_id=user.id, client_name="frontend").delete()
        db.add(UserToken(user_id=user.id, token_hash=new_hash, client_name="frontend"))

    # Commit so the user exists in DB before background import starts
    db.commit()

    # Kick off background import if user is in "importing" state
    if user.sync_status == "importing":
        mark_sync_started(user.id)
        background_tasks.add_task(_run_background_import, user.id, token_data["access_token"])

    return AuthCallbackResponse(
        user_id=user.id,
        display_name=user.display_name,
        access_token=token_data["access_token"],
        home_city=user.home_city_id,
        sync_status=user.sync_status,
    )


async def _run_background_import(user_id: int, access_token: str):
    """Run the activity import in the background after OAuth callback."""
    from app.database import get_session_factory
    from app.services.importer import ActivityImporter

    logger.info("Starting background import for user %d", user_id)
    factory = get_session_factory()
    session = factory()

    try:
        importer = ActivityImporter(db_session=session)
        result = await importer.import_phase_a(user_id=user_id, access_token=access_token)
        logger.info("Phase A complete for user %d: %s", user_id, result)

        user = session.get(User, user_id)
        if user:
            user.sync_status = "idle"
            user.last_sync_at = datetime.datetime.now(datetime.UTC)

        session.commit()
        logger.info("Import finished for user %d — %d activities imported", user_id, result.get("imported", 0))
    except Exception:
        logger.exception("Background import failed for user %d", user_id)
        session.rollback()
        try:
            user = session.get(User, user_id)
            if user:
                user.sync_status = "error"
                session.commit()
        except Exception:
            session.rollback()
    finally:
        mark_sync_finished(user_id)
        session.close()


@router.post("/logout", response_model=LogoutResponse)
def logout(
    db: Session = Depends(get_db),
    authorization: str = Header(None),
):
    """End user session — removes the current token."""
    if authorization:
        parts = authorization.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1].strip()
            if token:
                token_hash = compute_token_hash(token)
                db.query(UserToken).filter_by(token_hash=token_hash).delete()
                db.commit()
    return LogoutResponse(message="Logged out")


class MCPRegisterRequest(BaseModel):
    """Request body for MCP token registration."""
    access_token: str
    strava_athlete_id: int


@router.post("/mcp/register", response_model=AuthCallbackResponse)
def mcp_register(
    body: MCPRegisterRequest,
    db: Session = Depends(get_db),
):
    """Register an MCP server's Strava token for an existing user.

    The MCP server performs its own Strava OAuth, then calls this endpoint
    to register the token with the backend so it can make authenticated API calls.
    """
    user = db.query(User).filter_by(strava_athlete_id=body.strava_athlete_id).first()
    if not user:
        raise AppError("NOT_FOUND", "No user found for this Strava athlete", 404)

    new_hash = compute_token_hash(body.access_token)
    existing = db.query(UserToken).filter_by(token_hash=new_hash).first()
    if not existing:
        # Remove old MCP tokens for this user (one active MCP session)
        db.query(UserToken).filter_by(user_id=user.id, client_name="mcp").delete()
        db.add(UserToken(user_id=user.id, token_hash=new_hash, client_name="mcp"))
        db.commit()

    return AuthCallbackResponse(
        user_id=user.id,
        display_name=user.display_name,
        access_token=body.access_token,
        home_city=user.home_city_id,
        sync_status=user.sync_status,
    )
