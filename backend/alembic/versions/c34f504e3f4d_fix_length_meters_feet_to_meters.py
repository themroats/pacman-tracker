"""fix_length_meters_feet_to_meters

The load script projected to EPSG:2926 (WA State Plane North, US survey feet)
and stored .length as meters.  This migration recalculates every
street_segments.length_meters from PostGIS ST_Length(geography) which returns
true metres, then refreshes the cached totals on neighborhoods and cities.

Revision ID: c34f504e3f4d
Revises: 69ccd5bab23b
Create Date: 2026-03-29 11:37:57.549578
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c34f504e3f4d'
down_revision: Union[str, None] = '69ccd5bab23b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# US survey feet → metres
FT_TO_M = 0.3048006096012192


def upgrade() -> None:
    # 1. Recalculate street segment lengths from geography (true metres)
    op.execute("""
        UPDATE street_segments
        SET length_meters = ST_Length(geometry::geography)
        WHERE ST_Length(geometry::geography) > 0
    """)

    # 2. Refresh neighborhood cached totals
    op.execute("""
        UPDATE neighborhoods n
        SET total_street_length_m = COALESCE(sub.total, 0)
        FROM (
            SELECT neighborhood_id, SUM(length_meters) AS total
            FROM street_segments
            WHERE neighborhood_id IS NOT NULL
            GROUP BY neighborhood_id
        ) sub
        WHERE n.id = sub.neighborhood_id
    """)

    # 3. Refresh city cached totals
    op.execute("""
        UPDATE cities c
        SET total_street_length_m = COALESCE(sub.total, 0)
        FROM (
            SELECT city_id, SUM(length_meters) AS total
            FROM street_segments
            GROUP BY city_id
        ) sub
        WHERE c.id = sub.city_id
    """)


def downgrade() -> None:
    # Reverse: multiply by feet-per-metre to restore original (wrong) values
    op.execute("""
        UPDATE street_segments
        SET length_meters = length_meters / 0.3048006096012192
    """)

    op.execute("""
        UPDATE neighborhoods n
        SET total_street_length_m = COALESCE(sub.total, 0)
        FROM (
            SELECT neighborhood_id, SUM(length_meters) AS total
            FROM street_segments
            WHERE neighborhood_id IS NOT NULL
            GROUP BY neighborhood_id
        ) sub
        WHERE n.id = sub.neighborhood_id
    """)

    op.execute("""
        UPDATE cities c
        SET total_street_length_m = COALESCE(sub.total, 0)
        FROM (
            SELECT city_id, SUM(length_meters) AS total
            FROM street_segments
            GROUP BY city_id
        ) sub
        WHERE c.id = sub.city_id
    """)
