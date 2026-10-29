"""Модель лица (сотрудника) для распознавания."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Face(Base):
    """Сотрудник и его биометрический эталон (эмбеддинг лица)."""

    __tablename__ = "faces"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[str | None] = mapped_column(String(255), nullable=True)
    personnel_uid: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=True,
    )
    # Вектор эмбеддинга лица. Храним как JSON-массив; при необходимости
    # в одной из следующих фаз можно перевести на pgvector для поиска по подобию.
    embedding: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    photo_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # --- Связи ---
    zone_permissions: Mapped[list["ZonePermission"]] = relationship(
        back_populates="face",
        cascade="all, delete-orphan",
    )
    violations: Mapped[list["Violation"]] = relationship(back_populates="face")

    def __repr__(self) -> str:
        return f"<Face(id={self.id}, full_name={self.full_name!r})>"