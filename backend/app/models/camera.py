"""Модель камеры видеонаблюдения."""
from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Camera(Base):
    """Камера с RTSP-потоком и настройками."""

    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rtsp_url: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="offline",
        server_default="offline",
    )
    # Из ТЗ у камеры есть worker_id, но отдельной таблицы workers нет, а связка
    # "оператор <-> камера" описывается таблицей operator_camera. Поэтому храним
    # worker_id как внешний nullable-идентификатор без FK (при необходимости
    # навесим FK в отдельной миграции).
    worker_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # --- Связи ---
    zones: Mapped[list["Zone"]] = relationship(back_populates="camera")
    operators: Mapped[list["OperatorCamera"]] = relationship(back_populates="camera")
    violations: Mapped[list["Violation"]] = relationship(back_populates="camera")

    def __repr__(self) -> str:
        return f"<Camera(id={self.id}, name={self.name!r})>"