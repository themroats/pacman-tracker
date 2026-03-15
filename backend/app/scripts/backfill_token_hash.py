"""Backfill access_token_hash for existing users.

One-time migration script that decrypts each user's access token and
stores its SHA-256 hex digest in the new access_token_hash column.

Usage:
    python -m app.scripts.backfill_token_hash
"""

import logging
import sys

from sqlalchemy.orm import Session

from app.database import get_engine
from app.models.user import User
from app.services.crypto import compute_token_hash, decrypt_token

logger = logging.getLogger(__name__)


def backfill(session: Session) -> int:
    """Compute and store token hashes for all users missing one. Returns count updated."""
    users = session.query(User).filter(User.access_token_hash.is_(None)).all()
    updated = 0

    for user in users:
        try:
            plain_token = decrypt_token(user.access_token_encrypted)
            user.access_token_hash = compute_token_hash(plain_token)
            updated += 1
            logger.info("Backfilled token hash for user %d (%s)", user.id, user.display_name)
        except Exception:
            logger.exception("Failed to backfill token hash for user %d", user.id)

    if updated:
        session.commit()

    return updated


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    engine = get_engine()
    with Session(engine) as session:
        count = backfill(session)

    if count:
        logger.info("Backfilled %d user(s).", count)
    else:
        logger.info("All users already have token hashes. Nothing to do.")


if __name__ == "__main__":
    main()
