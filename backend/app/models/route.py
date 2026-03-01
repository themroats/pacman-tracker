"""RouteSuggestion and RouteSuggestionSegment ORM models (T054)."""

import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RouteSuggestion(Base):
    """A generated route suggestion for a user."""

    __tablename__ = "route_suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    city_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cities.id"), nullable=False
    )
    neighborhood_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("neighborhoods.id"), nullable=True
    )
    start_point: Mapped[str] = mapped_column(
        Geometry("POINT", srid=4326), nullable=False
    )
    route_geometry: Mapped[str] = mapped_column(
        Geometry("LINESTRING", srid=4326), nullable=False
    )
    distance_meters: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_distance_meters: Mapped[float] = mapped_column(Float, nullable=False)
    untraveled_distance_meters: Mapped[float] = mapped_column(Float, nullable=False)
    untraveled_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relationships
    user = relationship("User")
    city = relationship("City")
    neighborhood = relationship("Neighborhood")
    segments = relationship(
        "RouteSuggestionSegment",
        back_populates="route_suggestion",
        cascade="all, delete-orphan",
        order_by="RouteSuggestionSegment.sequence_order",
    )

    def __repr__(self) -> str:
        return (
            f"<RouteSuggestion(id={self.id}, user={self.user_id}, "
            f"dist={self.distance_meters:.0f}m)>"
        )


class RouteSuggestionSegment(Base):
    """Join table linking route suggestions to traversed street segments."""

    __tablename__ = "route_suggestion_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_suggestion_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("route_suggestions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    street_segment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("street_segments.id"), nullable=False
    )
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_untraveled: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # Relationships
    route_suggestion = relationship("RouteSuggestion", back_populates="segments")
    street_segment = relationship("StreetSegment")

    def __repr__(self) -> str:
        return (
            f"<RouteSuggestionSegment(route={self.route_suggestion_id}, "
            f"street={self.street_segment_id}, order={self.sequence_order})>"
        )
