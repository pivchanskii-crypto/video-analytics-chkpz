"""Связь зона <-> лицо (разрешения/white-list)."""
from __future__ import annotations

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ZonePermission(Base):
    """Разрешение конкретному лицу находиться/работать в зоне."""

    __tablename__ = "zone_permissions"

    # Составной первичный ключ (по ТЗ у таблицы нет отдельного id).
    zone_id: Mapped[int] = mapped_column(
        ForeignKey("zones.id", ondelete="CASCADE"),
        primary_key=True,
    )
    face_id: Mapped[int] = mapped_column(
        ForeignKey("faces.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # --- Связи ---
    zone: Mapped["Zone"] = relationship(back_populates="face_permissions")
    face: Mapped["Face"] = relationship(back_populates="zone_permissions")

    def __repr__(self) -> str:
        return f"<ZonePermission(zone_id={self.zone_id}, face_id={self.face_id})>"