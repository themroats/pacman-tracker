"""CoveragePlan, CoveragePlanRoute, and CoverageGoal ORM models."""

import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CoveragePlan(Base):
    """A plan to complete coverage of a specific neighborhood."""

    __tablename__ = "coverage_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    city_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cities.id"), nullable=False
    )
    neighborhood_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("neighborhoods.id"), nullable=False
    )
    goal_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("coverage_goals.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="generating"
    )
    preferred_route_distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    initial_coverage_pct: Mapped[float] = mapped_column(Float, nullable=False)
    target_coverage_pct: Mapped[float] = mapped_column(
        Float, nullable=False, default=100.0
    )
    total_routes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_distance_m: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    VALID_STATUSES = {"generating", "ready", "in_progress", "completed", "failed"}

    # Relationships
    user = relationship("User")
    city = relationship("City")
    neighborhood = relationship("Neighborhood")
    goal = relationship("CoverageGoal", back_populates="plans")
    routes = relationship(
        "CoveragePlanRoute",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="CoveragePlanRoute.sequence_order",
    )

    def __repr__(self) -> str:
        return (
            f"<CoveragePlan(id={self.id}, neighborhood={self.neighborhood_id}, "
            f"status={self.status!r})>"
        )


class CoveragePlanRoute(Base):
    """Join table linking a coverage plan to its generated route suggestions."""

    __tablename__ = "coverage_plan_routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("coverage_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    route_suggestion_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("route_suggestions.id"), nullable=False
    )
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    streets_targeted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    VALID_STATUSES = {"pending", "completed", "skipped"}

    # Relationships
    plan = relationship("CoveragePlan", back_populates="routes")
    route_suggestion = relationship("RouteSuggestion")

    def __repr__(self) -> str:
        return (
            f"<CoveragePlanRoute(plan={self.plan_id}, order={self.sequence_order}, "
            f"status={self.status!r})>"
        )


class CoverageGoal(Base):
    """A city-level coverage target linking to multiple neighborhood plans."""

    __tablename__ = "coverage_goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    city_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cities.id"), nullable=False
    )
    target_coverage_pct: Mapped[float] = mapped_column(Float, nullable=False)
    current_coverage_pct: Mapped[float] = mapped_column(Float, nullable=False)
    preferred_route_distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="analyzing"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    VALID_STATUSES = {"analyzing", "ready", "in_progress", "completed"}

    # Relationships
    user = relationship("User")
    city = relationship("City")
    plans = relationship(
        "CoveragePlan",
        back_populates="goal",
        order_by="CoveragePlan.id",
    )

    def __repr__(self) -> str:
        return (
            f"<CoverageGoal(id={self.id}, city={self.city_id}, "
            f"target={self.target_coverage_pct}%)>"
        )
