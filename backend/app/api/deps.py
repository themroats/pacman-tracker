"""
Shared authentication dependency for FastAPI route handlers.

Validates the Bearer token from the Authorization header by looking up
the user whose encrypted access token matches.
"""

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import AppError
from app.models.user import User
from app.services.crypto import decrypt_token


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
    """
    if not authorization:
        raise AppError("UNAUTHORIZED", "Missing authorization header", 401)

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AppError("UNAUTHORIZED", "Invalid authorization header format", 401)

    token = parts[1].strip()
    if not token:
        raise AppError("UNAUTHORIZED", "Empty bearer token", 401)

    # Look up by decrypting stored tokens
    users = db.query(User).all()
    for user in users:
        try:
            stored_token = decrypt_token(user.access_token_encrypted)
            if stored_token == token:
                return user
        except Exception:
            continue

    raise AppError("UNAUTHORIZED", "Invalid or expired token", 401)
