"""Связь оператор <-> камера."""
from __future__ import annotations

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class OperatorCamera(Base):
    """Назначение камеры оператору."""

    __tablename__ = "operator_camera"

    # Составной первичный ключ (по ТЗ у таблицы нет отдельного id).
    operator_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    camera_id: Mapped[int] = mapped_column(
        ForeignKey("cameras.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # --- Связи ---
    operator: Mapped["User"] = relationship(back_populates="operator_cameras")
    camera: Mapped["Camera"] = relationship(back_populates="operators")

    def __repr__(self) -> str:
        return f"<OperatorCamera(operator_id={self.operator_id}, camera_id={self.camera_id})>"