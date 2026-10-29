"""Модель нарушения."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import IdentityStatus, ViolationStatus, ViolationType
from app.core.types import sa_enum


class Violation(Base):
    """Зафиксированное нарушение (отсутствие СИЗ, вход в зону и т.д.)."""

    __tablename__ = "violations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    camera_id: Mapped[int] = mapped_column(
        ForeignKey("cameras.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("zones.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    track_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    type: Mapped[ViolationType] = mapped_column(
        sa_enum(ViolationType, "violation_type"),
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    frame_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    face_id: Mapped[int | None] = mapped_column(
        ForeignKey("faces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    identity_status: Mapped[IdentityStatus] = mapped_column(
        sa_enum(IdentityStatus, "identity_status"),
        nullable=False,
        default=IdentityStatus.NOT_APPLICABLE,
        server_default=IdentityStatus.NOT_APPLICABLE.value,
    )
    status: Mapped[ViolationStatus] = mapped_column(
        sa_enum(ViolationStatus, "violation_status"),
        nullable=False,
        default=ViolationStatus.OPEN,
        server_default=ViolationStatus.OPEN.value,
    )

    # --- Связи ---
    camera: Mapped["Camera"] = relationship(back_populates="violations")
    zone: Mapped["Zone"] = relationship(back_populates="violations")
    face: Mapped["Face"] = relationship(back_populates="violations")
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="violation",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Violation(id={self.id}, type={self.type})>"