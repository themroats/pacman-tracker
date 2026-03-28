"""
Shared authentication dependency for FastAPI route handlers.

Validates the Bearer token from the Authorization header by looking up
the user whose encrypted access token matches.
"""

import logging

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.errors import AppError
from app.models.user import User
from app.services.crypto import compute_token_hash

logger = logging.getLogger(__name__)


def get_current_user(
    db: Session = Depends(get_db),
    authorization: str = Header(None),
) -> User:
    """Extract and validate the current user from the Authorization header.

    Expects: ``Authorization: Bearer <access_token>``

    The token is the raw Strava access token returned at login.  We find
    the user by decrypting each stored token and comparing.  For a small
    number of users (local dev) this is fine; a production app would use
    JWT or a session table.

    When ``DEV_AUTH_BYPASS=1`` is set in the environment, the token check
    is skipped and the first user in the database is returned.  This is
    only intended for local development.
    """
    settings = get_settings()

    # --- Dev bypass: skip token validation, return first user -----------
    if settings.dev_auth_bypass:
        logger.critical(
            "DEV_AUTH_BYPASS is enabled — all requests authenticate as the first user. "
            "This MUST NOT be used in production."
        )
        user = db.query(User).first()
        if user:
            return user
        raise AppError("UNAUTHORIZED", "DEV_AUTH_BYPASS is on but no users exist", 401)

    # --- Normal token-based auth ----------------------------------------
    if not authorization:
        raise AppError("UNAUTHORIZED", "Missing authorization header", 401)

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AppError("UNAUTHORIZED", "Invalid authorization header format", 401)

    token = parts[1].strip()
    if not token:
        raise AppError("UNAUTHORIZED", "Empty bearer token", 401)

    # O(1) lookup via indexed SHA-256 hash of the plaintext token
    token_hash = compute_token_hash(token)
    user = db.query(User).filter_by(access_token_hash=token_hash).first()
    if user:
        return user

    raise AppError("UNAUTHORIZED", "Invalid or expired token", 401)
