"""UserStartPoint ORM model — saved favorite start locations."""

import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserStartPoint(Base):
    """A named start point saved by a user for route suggestions."""

    __tablename__ = "user_start_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    point: Mapped[str] = mapped_column(
        Geometry("POINT", srid=4326), nullable=False
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    # Relationships
    user = relationship("User")

    def __repr__(self) -> str:
        return f"<UserStartPoint(id={self.id}, name={self.name!r}, default={self.is_default})>"
