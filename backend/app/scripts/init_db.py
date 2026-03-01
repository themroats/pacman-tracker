"""
Database initialisation script.

Creates all tables and spatial indexes.
Usage: python -m app.scripts.init_db
"""

import sys
from pathlib import Path

from sqlalchemy import text

# Ensure models are imported so Base.metadata is populated
from app.database import Base, create_db_engine
from app.models.city import City  # noqa: F401
from app.models.neighborhood import Neighborhood  # noqa: F401
from app.models.street import StreetSegment  # noqa: F401
from app.models.user import User  # noqa: F401


def init_db(database_url: str | None = None) -> None:
    """Create all tables and spatial indexes."""
    engine = create_db_engine(database_url)

    # Ensure data directory exists for SQLite
    from app.config import get_settings

    settings = get_settings()
    url = database_url or settings.database_url
    if url.startswith("sqlite"):
        db_path = url.replace("sqlite:///", "")
        if db_path.startswith("./"):
            db_path = db_path[2:]
        parent = Path(db_path).parent
        parent.mkdir(parents=True, exist_ok=True)

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create spatial indexes (SpatiaLite uses R-tree via triggers)
    with engine.connect() as conn:
        # Check if using SpatiaLite
        try:
            conn.execute(text("SELECT spatialite_version()"))
            is_spatialite = True
        except Exception:
            is_spatialite = False

        if is_spatialite:
            _create_spatialite_indexes(conn)
        else:
            _create_postgis_indexes(conn)

        conn.commit()

    print("Database initialized successfully.")


def _create_spatialite_indexes(conn) -> None:
    """Create SpatiaLite R-tree spatial indexes."""
    spatial_tables = [
        ("street_segments", "geometry"),
        ("cities", "boundary"),
        ("neighborhoods", "boundary"),
    ]
    for table, column in spatial_tables:
        # SpatiaLite creates R-tree indexes via CreateSpatialIndex
        try:
            conn.execute(
                text(f"SELECT CreateSpatialIndex('{table}', '{column}')")
            )
        except Exception:
            # Index may already exist
            pass


def _create_postgis_indexes(conn) -> None:
    """Create PostGIS GIST spatial indexes."""
    indexes = [
        "CREATE INDEX IF NOT EXISTS ix_street_segments_geometry ON street_segments USING GIST (geometry)",
        "CREATE INDEX IF NOT EXISTS ix_cities_boundary ON cities USING GIST (boundary)",
        "CREATE INDEX IF NOT EXISTS ix_neighborhoods_boundary ON neighborhoods USING GIST (boundary)",
    ]
    for idx in indexes:
        conn.execute(text(idx))


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else None
    init_db(url)
