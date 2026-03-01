"""User ORM model."""

import datetime

from geoalchemy2 import Management
from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """Represents an authenticated Strava user."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strava_athlete_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    profile_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    token_expires_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    strava_scope: Mapped[str] = mapped_column(String(100), nullable=False)
    home_city_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True  # FK added after City model is defined
    )
    last_sync_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    sync_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="idle"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    activities = relationship("Activity", back_populates="user", lazy="dynamic")

    VALID_SYNC_STATUSES = {"idle", "importing", "syncing", "error", "revoked"}

    def __repr__(self) -> str:
        return f"<User(id={self.id}, strava_athlete_id={self.strava_athlete_id}, name={self.display_name!r})>"
