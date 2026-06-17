"""
Safety guard for verification-harness scripts (feature 008).

Every seed/reset/snapshot-restore operation MUST run ONLY against the dedicated,
isolated verification database. This module resolves the target database name and
refuses (exit code 4) if it does not match the configured verification database,
so the developer's primary dev/prod database can never be mutated by mistake.
"""

from __future__ import annotations

import sys
from urllib.parse import urlparse

from app.config import get_settings

# Shared exit code used by all verification scripts when the target DB is refused.
EXIT_REFUSED_NOT_VERIFICATION_DB = 4


def _database_name(url: str) -> str:
    """Extract the database name from a PostgreSQL URL."""
    return urlparse(url).path.lstrip("/")


def resolve_verification_url(database_url: str | None) -> str:
    """
    Return the verification database URL to operate on.

    Falls back to the configured ``verification_database_url`` when no explicit
    URL is supplied.
    """
    if database_url:
        return database_url
    return get_settings().verification_database_url


def assert_verification_db(database_url: str) -> None:
    """
    Verify that *database_url* points at the configured verification database.

    Compares by database name (not full URL) so host/credential differences do
    not matter. Exits the process with code 4 on mismatch.
    """
    settings = get_settings()
    expected = _database_name(settings.verification_database_url)
    actual = _database_name(database_url)

    if not expected:
        print(
            "Refusing to run: VERIFICATION_DATABASE_URL has no database name configured.",
            file=sys.stderr,
        )
        sys.exit(EXIT_REFUSED_NOT_VERIFICATION_DB)

    if actual != expected:
        print(
            "Refusing to run verification script against database "
            f"{actual!r}; only the isolated verification database {expected!r} "
            "is allowed. Set --database-url / VERIFICATION_DATABASE_URL correctly.",
            file=sys.stderr,
        )
        sys.exit(EXIT_REFUSED_NOT_VERIFICATION_DB)


def is_verification_db(database_url: str) -> bool:
    """Non-exiting variant of :func:`assert_verification_db` for tests."""
    settings = get_settings()
    expected = _database_name(settings.verification_database_url)
    return bool(expected) and _database_name(database_url) == expected
