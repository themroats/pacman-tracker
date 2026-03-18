"""Validate referential integrity before enabling PRAGMA foreign_keys = ON.

Run once before deploying the FK-enforcement change to identify and clean
orphaned records that would violate foreign-key constraints.

Usage:
    python -m app.scripts.validate_fk_integrity [--fix]
"""

import argparse
import logging
import sys

from app.database import get_engine, Base
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


def check_orphans(session: Session, *, fix: bool = False) -> int:
    """Return the number of orphaned rows found (and optionally delete them)."""
    issues = 0

    checks = [
        (
            "activities without users",
            "SELECT COUNT(*) FROM activities WHERE user_id NOT IN (SELECT id FROM users)",
            "DELETE FROM activities WHERE user_id NOT IN (SELECT id FROM users)",
        ),
        (
            "activities with invalid city_id",
            "SELECT COUNT(*) FROM activities WHERE city_id IS NOT NULL AND city_id NOT IN (SELECT id FROM cities)",
            "UPDATE activities SET city_id = NULL WHERE city_id IS NOT NULL AND city_id NOT IN (SELECT id FROM cities)",
        ),
        (
            "user_street_coverages without users",
            "SELECT COUNT(*) FROM user_street_coverages WHERE user_id NOT IN (SELECT id FROM users)",
            "DELETE FROM user_street_coverages WHERE user_id NOT IN (SELECT id FROM users)",
        ),
        (
            "user_street_coverages without street_segments",
            "SELECT COUNT(*) FROM user_street_coverages WHERE street_segment_id NOT IN (SELECT id FROM street_segments)",
            "DELETE FROM user_street_coverages WHERE street_segment_id NOT IN (SELECT id FROM street_segments)",
        ),
        (
            "street_segments without cities",
            "SELECT COUNT(*) FROM street_segments WHERE city_id NOT IN (SELECT id FROM cities)",
            "DELETE FROM street_segments WHERE city_id NOT IN (SELECT id FROM cities)",
        ),
        (
            "neighborhoods without cities",
            "SELECT COUNT(*) FROM neighborhoods WHERE city_id NOT IN (SELECT id FROM cities)",
            "DELETE FROM neighborhoods WHERE city_id NOT IN (SELECT id FROM cities)",
        ),
    ]

    for description, count_sql, fix_sql in checks:
        try:
            (count,) = session.execute(text(count_sql)).one()
        except Exception:
            logger.info("Skipping check for %s (table may not exist)", description)
            continue

        if count > 0:
            issues += count
            logger.warning("Found %d %s", count, description)
            if fix:
                session.execute(text(fix_sql))
                logger.info("Fixed: %s", description)
        else:
            logger.info("OK: %s", description)

    if fix and issues:
        session.commit()
        logger.info("All orphaned records cleaned up")

    return issues


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate FK integrity")
    parser.add_argument("--fix", action="store_true", help="Delete/fix orphaned records")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    engine = get_engine()
    with Session(engine) as session:
        issues = check_orphans(session, fix=args.fix)

    if issues and not args.fix:
        logger.error(
            "Found %d orphaned records. Re-run with --fix to clean them up.", issues
        )
        sys.exit(1)
    elif issues:
        logger.info("Cleaned up %d orphaned records.", issues)
    else:
        logger.info("No orphaned records found. FK enforcement is safe to enable.")


if __name__ == "__main__":
    main()
