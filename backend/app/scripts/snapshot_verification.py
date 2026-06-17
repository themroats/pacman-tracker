"""
Frozen Seattle snapshot tooling for the verification harness.

Provides two subcommands:

* ``build``   — ``pg_dump`` the street baseline tables (``cities``,
  ``neighborhoods``, ``street_segments``) ONLY from a source PostGIS database to
  a local artifact (gitignored; not committed). No user/activity/coverage tables
  are dumped, so no private data is ever captured.
* ``restore`` — restore that artifact into the isolated verification database
  (guarded so it can only target the verification DB).

Usage::

    python -m app.scripts.snapshot_verification build --output path/to/seattle.dump
    python -m app.scripts.snapshot_verification restore --input path/to/seattle.dump \
        --database-url postgresql://.../pacman_verify
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from urllib.parse import urlparse

from sqlalchemy import text

from app.config import get_settings
from app.database import create_db_engine
from app.scripts._verify_guard import assert_verification_db, resolve_verification_url

# Baseline tables that form the frozen street snapshot. Order matters for
# foreign keys on restore (cities -> neighborhoods -> street_segments).
SNAPSHOT_TABLES = ["cities", "neighborhoods", "street_segments"]

EXIT_SOURCE_MISSING_TABLES = 2
EXIT_DUMP_FAILED = 3
EXIT_RESTORE_FAILED = 5


def _pg_env(url: str) -> dict[str, str]:
    """Build an environment dict with PGPASSWORD for pg_dump/pg_restore."""
    parsed = urlparse(url)
    env = os.environ.copy()
    if parsed.password:
        env["PGPASSWORD"] = parsed.password
    return env


def _conn_args(url: str) -> list[str]:
    """Translate a PostgreSQL URL into pg_* CLI connection flags."""
    parsed = urlparse(url)
    args: list[str] = []
    if parsed.hostname:
        args += ["-h", parsed.hostname]
    if parsed.port:
        args += ["-p", str(parsed.port)]
    if parsed.username:
        args += ["-U", parsed.username]
    args += ["-d", parsed.path.lstrip("/")]
    return args


def build(source_url: str, output: str) -> int:
    """Dump the snapshot tables from *source_url* into *output* (custom format)."""
    cmd = ["pg_dump", *_conn_args(source_url), "-Fc", "--no-owner", "--no-privileges"]
    for table in SNAPSHOT_TABLES:
        cmd += ["-t", table]
    cmd += ["-f", output]

    print(f"Dumping {', '.join(SNAPSHOT_TABLES)} -> {output}")
    try:
        result = subprocess.run(cmd, env=_pg_env(source_url), capture_output=True, text=True)
    except FileNotFoundError:
        print("pg_dump not found on PATH. Install PostgreSQL client tools.", file=sys.stderr)
        return EXIT_DUMP_FAILED
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    if result.returncode != 0:
        lowered = result.stderr.lower()
        if "no matching tables were found" in lowered or "does not exist" in lowered:
            print("Source database is missing required snapshot tables.", file=sys.stderr)
            return EXIT_SOURCE_MISSING_TABLES
        print(f"pg_dump failed (exit {result.returncode}).", file=sys.stderr)
        return EXIT_DUMP_FAILED
    print("Snapshot build complete.")
    return 0


def restore(target_url: str, input_path: str) -> int:
    """Restore *input_path* into the (guarded) verification database."""
    assert_verification_db(target_url)

    if not os.path.exists(input_path):
        print(f"Snapshot artifact not found: {input_path}", file=sys.stderr)
        return EXIT_RESTORE_FAILED

    # Idempotency: clear any existing snapshot rows first so re-running restore on
    # a non-empty verification DB does not fail with duplicate-key errors. CASCADE
    # also drops dependent demo rows (coverage/activities), which the seed step
    # recreates afterwards.
    engine = create_db_engine(target_url)
    try:
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE {', '.join(SNAPSHOT_TABLES)} RESTART IDENTITY CASCADE"))
    finally:
        engine.dispose()

    # --data-only loads the baseline rows into tables that already exist (created
    # by `alembic upgrade head`). The dump's TOC order (cities -> neighborhoods ->
    # street_segments) satisfies foreign keys during the load.
    cmd = [
        "pg_restore",
        *_conn_args(target_url),
        "--data-only",
        "--no-owner",
        "--no-privileges",
        input_path,
    ]
    print(f"Restoring {input_path} -> {urlparse(target_url).path.lstrip('/')}")
    try:
        subprocess.run(cmd, env=_pg_env(target_url), check=True)
    except FileNotFoundError:
        print("pg_restore not found on PATH. Install PostgreSQL client tools.", file=sys.stderr)
        return EXIT_RESTORE_FAILED
    except subprocess.CalledProcessError as exc:
        print(f"pg_restore failed (exit {exc.returncode}).", file=sys.stderr)
        return EXIT_RESTORE_FAILED
    print("Snapshot restore complete.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build/restore the frozen Seattle snapshot.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="Dump the street baseline to an artifact.")
    p_build.add_argument(
        "--source-url",
        default=get_settings().database_url,
        help="Source PostGIS database URL (defaults to DATABASE_URL).",
    )
    p_build.add_argument("--output", required=True, help="Output artifact path.")

    p_restore = sub.add_parser("restore", help="Restore an artifact into the verification DB.")
    p_restore.add_argument("--input", required=True, help="Snapshot artifact path.")
    p_restore.add_argument(
        "--database-url",
        default=None,
        help="Target verification database URL (defaults to VERIFICATION_DATABASE_URL).",
    )

    args = parser.parse_args(argv)

    if args.command == "build":
        return build(args.source_url, args.output)
    if args.command == "restore":
        return restore(resolve_verification_url(args.database_url), args.input)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
