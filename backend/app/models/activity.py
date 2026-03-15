"""Activity ORM model."""

import datetime

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Activity(Base):
    """A single exercise session imported from Strava."""

    __tablename__ = "activities"
    __table_args__ = (
        Index("ix_activity_user_start_date", "user_id", "start_date"),
        Index("ix_activity_user_sport_type", "user_id", "sport_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    strava_activity_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sport_type: Mapped[str] = mapped_column(String(50), nullable=False)
    start_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    distance_meters: Mapped[float] = mapped_column(Float, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    moving_time_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    summary_polyline: Mapped[str | None] = mapped_column(Text, nullable=True)
    detailed_polyline: Mapped[str | None] = mapped_column(Text, nullable=True)
    gps_trace: Mapped[str | None] = mapped_column(
        Geometry("LINESTRING", srid=4326),
        nullable=True,
    )
    has_gps: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_on_street: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    import_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    city_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("cities.id"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relationships
    user = relationship("User", back_populates="activities")

    VALID_IMPORT_STATUSES = {"pending", "polyline_imported", "streams_imported", "matched"}

    @property
    def pace_min_per_km(self) -> float | None:
        """Compute pace in minutes per kilometer."""
        if self.distance_meters and self.distance_meters > 0:
            return (self.moving_time_seconds / 60) / (self.distance_meters / 1000)
        return None

    def __repr__(self) -> str:
        return (
            f"<Activity(id={self.id}, strava_id={self.strava_activity_id}, "
            f"name={self.name!r}, sport={self.sport_type})>"
        )
