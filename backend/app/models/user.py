"""Модель пользователя платформы."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import UserRole
from app.core.types import sa_enum


class User(Base):
    """Пользователь платформы: администратор или оператор."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    login: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # Email для доставки оповещений (Фаза 5). Если не задан, получателем
    # считается ``login`` (считаем, что login оператора — это и есть его email).
    email: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        sa_enum(UserRole, "user_role"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # --- Связи ---
    operator_cameras: Mapped[list["OperatorCamera"]] = relationship(
        back_populates="operator",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, login={self.login!r}, role={self.role})>"