"""StreetSegment ORM model."""

import datetime

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class StreetSegment(Base):
    """A section of road/sidewalk from the OpenStreetMap network."""

    __tablename__ = "street_segments"
    __table_args__ = (
        Index("ix_street_segment_city_neighborhood", "city_id", "neighborhood_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    city_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cities.id"), nullable=False, index=True
    )
    neighborhood_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("neighborhoods.id"), nullable=True, index=True
    )
    osm_way_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    osm_node_start: Mapped[int] = mapped_column(BigInteger, nullable=False)
    osm_node_end: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    highway_type: Mapped[str] = mapped_column(String(50), nullable=False)
    geometry: Mapped[str] = mapped_column(
        Geometry("LINESTRING", srid=4326),
        nullable=False,
    )
    length_meters: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relationships
    city = relationship("City", back_populates="street_segments")
    neighborhood = relationship("Neighborhood", back_populates="street_segments")

    def __repr__(self) -> str:
        return (
            f"<StreetSegment(id={self.id}, osm_way_id={self.osm_way_id}, "
            f"name={self.name!r})>"
        )
