"""Сервисный слой прав доступа (роль → видимость камер)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.enums import UserRole
from app.models.operator_camera import OperatorCamera
from app.models.user import User


def assigned_camera_ids(db: Session, user: User) -> set[int] | None:
    """Возвращает id камер, доступных пользователю.

    Для администратора возвращает ``None`` (доступ ко всем камерам). Для оператора
    возвращает множество id камер из связки ``operator_camera`` (возможно пустое).
    """
    if user.role == UserRole.ADMIN:
        return None

    rows = (
        db.query(OperatorCamera.camera_id)
        .filter(OperatorCamera.operator_id == user.id)
        .all()
    )
    return {camera_id for (camera_id,) in rows}