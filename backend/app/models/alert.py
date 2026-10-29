"""Модель оповещения (алерта)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Alert(Base):
    """Оповещение по нарушению (отправлено или запланировано)."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    violation_id: Mapped[int] = mapped_column(
        ForeignKey("violations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Канал доставки (email, telegram, sms и т.п.).
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    # --- Связи ---
    violation: Mapped["Violation"] = relationship(back_populates="alerts")

    def __repr__(self) -> str:
        return f"<Alert(id={self.id}, channel={self.channel!r}, status={self.status!r})>"