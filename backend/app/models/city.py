"""City ORM model."""

import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class City(Base):
    """A top-level geographic boundary for a supported city."""

    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    country: Mapped[str] = mapped_column(String(50), nullable=False, default="US")
    boundary: Mapped[str] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326),
        nullable=False,
    )
    projected_crs: Mapped[str] = mapped_column(String(20), nullable=False)
    total_street_segments: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    total_street_length_m: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    osm_data_updated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relationships
    neighborhoods = relationship("Neighborhood", back_populates="city", lazy="dynamic")
    street_segments = relationship(
        "StreetSegment", back_populates="city", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<City(id={self.id}, name={self.name!r}, state={self.state!r})>"
