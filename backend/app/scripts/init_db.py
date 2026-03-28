"""
Database initialisation script.

Creates all tables via SQLAlchemy metadata. PostGIS GiST indexes are created
automatically by GeoAlchemy2 geometry columns.

Usage: python -m app.scripts.init_db
"""

import sys

from sqlalchemy import text

# Ensure models are imported so Base.metadata is populated
from app.database import Base, create_db_engine
from app.models.city import City  # noqa: F401
from app.models.neighborhood import Neighborhood  # noqa: F401
from app.models.street import StreetSegment  # noqa: F401
from app.models.user import User  # noqa: F401


def init_db(database_url: str | None = None) -> None:
    """Create all tables and ensure PostGIS extension is available."""
    engine = create_db_engine(database_url)

    # Create all tables
    Base.metadata.create_all(bind=engine)

    print("Database initialized successfully.")


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else None
    init_db(url)
