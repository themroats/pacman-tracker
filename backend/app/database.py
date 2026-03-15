"""
Database engine, session management, and SpatiaLite extension loading.
"""

import logging
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""

    pass


def _load_spatialite(dbapi_conn, connection_record):
    """Load the SpatiaLite extension on every new SQLite connection."""
    dbapi_conn.enable_load_extension(True)
    for lib_name in ("mod_spatialite", "libspatialite"):
        try:
            dbapi_conn.load_extension(lib_name)
            break
        except Exception:
            continue
    else:
        logger.warning(
            "SpatiaLite extension not found. "
            "Spatial queries will not work. "
            "Install SpatiaLite to enable geospatial features."
        )
    dbapi_conn.enable_load_extension(False)


def _ensure_sqlite_parent_dir(url: str) -> None:
    """Create the parent directory for a file-based SQLite database if needed."""
    if not url.startswith("sqlite:///") or url == "sqlite:///:memory:":
        return

    db_path = url.replace("sqlite:///", "", 1)
    if not db_path:
        return

    # SQLAlchemy uses four slashes for absolute paths: sqlite:////home/data/app.db
    if url.startswith("sqlite:////") and not db_path.startswith("/"):
        db_path = f"/{db_path}"

    parent = Path(db_path).expanduser().resolve().parent
    parent.mkdir(parents=True, exist_ok=True)


def create_db_engine(database_url: str | None = None):
    """
    Create a SQLAlchemy engine.

    For SQLite URLs, registers a listener to load SpatiaLite on every connect.
    """
    settings = get_settings()
    url = database_url or settings.database_url

    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        _ensure_sqlite_parent_dir(url)

    engine = create_engine(url, connect_args=connect_args, echo=False)

    if url.startswith("sqlite"):
        event.listen(engine, "connect", _load_spatialite)
        # Initialise SpatiaLite metadata (idempotent)
        with engine.connect() as conn:
            conn.execute(text("SELECT InitSpatialMetaData(1)"))
            conn.commit()

    return engine


# Default engine and session factory (lazy-initialised)
_engine = None
_SessionLocal = None


def get_engine():
    """Return the singleton database engine."""
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine


def get_session_factory() -> sessionmaker:
    """Return the singleton session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a database session."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine():
    """Reset the singleton engine (useful for tests)."""
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None
