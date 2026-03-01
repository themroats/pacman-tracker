"""Coverage ORM models — tracks which streets a user has traveled and progress snapshots."""

import datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserStreetCoverage(Base):
    """One row per user per street segment — records how much of the street has been covered."""

    __tablename__ = "user_street_coverages"
    __table_args__ = (
        UniqueConstraint("user_id", "street_segment_id", name="uq_user_street"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    street_segment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("street_segments.id"), nullable=False, index=True
    )
    coverage_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_traveled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    first_traveled_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    last_activity_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("activities.id"), nullable=True
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user = relationship("User")
    street_segment = relationship("StreetSegment")
    last_activity = relationship("Activity")

    # Threshold constant
    TRAVELED_THRESHOLD = 0.80

    def __repr__(self) -> str:
        return (
            f"<UserStreetCoverage(user={self.user_id}, street={self.street_segment_id}, "
            f"ratio={self.coverage_ratio:.2f}, traveled={self.is_traveled})>"
        )


class CoverageSnapshot(Base):
    """A point-in-time record of a user's street coverage for progress/milestone tracking."""

    __tablename__ = "coverage_snapshots"
    __table_args__ = (
        UniqueConstraint("user_id", "city_id", "neighborhood_id", "snapshot_date", name="uq_snapshot"),
    )

    MILESTONE_THRESHOLDS = [25.0, 50.0, 75.0, 100.0]
    VALID_MILESTONE_LABELS = ["25%", "50%", "75%", "100%"]

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    city_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cities.id"), nullable=False, index=True
    )
    neighborhood_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("neighborhoods.id"), nullable=True
    )
    coverage_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    total_streets_traveled: Mapped[int] = mapped_column(Integer, nullable=False)
    total_streets: Mapped[int] = mapped_column(Integer, nullable=False)
    is_milestone: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    milestone_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    snapshot_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relationships
    user = relationship("User")
    city = relationship("City")
    neighborhood = relationship("Neighborhood")

    def __repr__(self) -> str:
        return (
            f"<CoverageSnapshot(user={self.user_id}, city={self.city_id}, "
            f"date={self.snapshot_date}, pct={self.coverage_percentage:.1f}%, "
            f"milestone={self.milestone_label})>"
        )
