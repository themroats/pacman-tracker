"""
Database engine, session management, and PostGIS extension initialization.
"""

import logging
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""

    pass


def _init_postgis(engine) -> None:
    """Ensure the PostGIS extension is available on the connected database."""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.commit()


def _validate_postgis(engine) -> None:
    """Verify PostgreSQL connection and PostGIS extension at startup."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT PostGIS_Version()"))
            version = result.scalar()
            logger.info("PostGIS version: %s", version)
    except Exception as exc:
        raise RuntimeError(
            f"Database startup validation failed: {exc}. "
            "Ensure PostgreSQL is running and PostGIS extension is installed."
        ) from exc


def _get_azure_token_creator(url: str):
    """Return a connection creator that uses Azure Managed Identity tokens."""
    import psycopg2
    from urllib.parse import urlparse

    parsed = urlparse(url)

    def _creator():
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential()
        token = credential.get_token(
            "https://ossrdbms-aad.database.windows.net/.default"
        )
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            dbname=parsed.path.lstrip("/"),
            user=parsed.username,
            password=token.token,
            sslmode="require",
        )
        return conn

    return _creator


def create_db_engine(database_url: str | None = None):
    """
    Create a SQLAlchemy engine for PostgreSQL + PostGIS.
    """
    settings = get_settings()
    url = database_url or settings.database_url

    engine_kwargs: dict = {
        "echo": False,
        "pool_size": settings.pool_size,
        "max_overflow": settings.max_overflow,
        "pool_pre_ping": True,
    }

    # Use Azure Managed Identity when connecting to Azure PG (no password in URL)
    if settings.use_azure_identity and "database.azure.com" in url:
        engine_kwargs["creator"] = _get_azure_token_creator(url)

    engine = create_engine(url, **engine_kwargs)

    _init_postgis(engine)
    _validate_postgis(engine)
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
