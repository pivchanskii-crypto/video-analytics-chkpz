"""Агрегирует все ORM-модели для Alembic и удобного импорта.

Импорт каждого модуля регистрирует модель в ``Base.metadata``.
"""
from __future__ import annotations

from app.models.alert import Alert
from app.models.audit_log import AuditLog
from app.models.camera import Camera
from app.models.face import Face
from app.models.operator_camera import OperatorCamera
from app.models.user import User
from app.models.violation import Violation
from app.models.zone import Zone
from app.models.zone_permission import ZonePermission

__all__ = [
    "User",
    "Camera",
    "Zone",
    "ZonePermission",
    "OperatorCamera",
    "Face",
    "Violation",
    "Alert",
    "AuditLog",
]