"""Модель зоны на кадре камеры."""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import CheckType
from app.core.types import sa_enum


class Zone(Base):
    """Полигон-зона внутри кадра с правилом проверки.

    Координаты полигона нормализованы и лежат в диапазоне ``[0, 1]``.
    """

    __tablename__ = "zones"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    camera_id: Mapped[int] = mapped_column(
        ForeignKey("cameras.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    polygon: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    check_type: Mapped[CheckType] = mapped_column(
        sa_enum(CheckType, "check_type"),
        nullable=False,
        default=CheckType.ZONE_ONLY,
        server_default=CheckType.ZONE_ONLY.value,
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    # --- Связи ---
    camera: Mapped["Camera"] = relationship(back_populates="zones")
    face_permissions: Mapped[list["ZonePermission"]] = relationship(
        back_populates="zone",
        cascade="all, delete-orphan",
    )
    violations: Mapped[list["Violation"]] = relationship(back_populates="zone")

    def __repr__(self) -> str:
        return f"<Zone(id={self.id}, name={self.name!r})>"