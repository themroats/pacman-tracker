"""UserToken ORM model — supports multiple active tokens per user."""

import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserToken(Base):
    """An active access token for a user, tagged by client type."""

    __tablename__ = "user_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    client_name: Mapped[str] = mapped_column(
        String(50), nullable=False, default="frontend"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    user = relationship("User", back_populates="tokens")

    def __repr__(self) -> str:
        return f"<UserToken(id={self.id}, user_id={self.user_id}, client={self.client_name!r})>"
