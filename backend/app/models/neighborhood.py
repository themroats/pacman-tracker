"""Neighborhood ORM model."""

import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Neighborhood(Base):
    """A named geographic area within a city."""

    __tablename__ = "neighborhoods"
    __table_args__ = (
        UniqueConstraint("city_id", "name", name="uq_neighborhood_city_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    city_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cities.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    boundary: Mapped[str] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326),
        nullable=False,
    )
    total_street_segments: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    total_street_length_m: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relationships
    city = relationship("City", back_populates="neighborhoods")
    street_segments = relationship(
        "StreetSegment", back_populates="neighborhood", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<Neighborhood(id={self.id}, name={self.name!r}, city_id={self.city_id})>"
