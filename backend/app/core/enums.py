"""Перечисления предметной области, используемые в моделях БД.

Значения хранятся как строки (``native_enum=False``), поэтому они совпадают
со значениями, описанными в ТЗ.
"""
from __future__ import annotations

import enum


class StrEnum(str, enum.Enum):
    """Базовый строковый enum — удобнее для JSON-сериализации и логов."""

    def __str__(self) -> str:
        return self.value


class UserRole(StrEnum):
    """Роль пользователя."""

    ADMIN = "admin"
    OPERATOR = "operator"


class CheckType(StrEnum):
    """Тип проверки зоны."""

    PRE_IN_ZONE = "pre_in_zone"
    ZONE_ONLY = "zone_only"
    DISABLED = "disabled"


class ViolationType(StrEnum):
    """Тип нарушения."""

    NO_PRE = "no_pre"
    ZONE_ENTRY = "zone_entry"
    UNAUTHORIZED = "unauthorized"


class IdentityStatus(StrEnum):
    """Статус идентификации лица в нарушении."""

    IDENTIFIED = "identified"
    UNKNOWN = "unknown"
    UNCERTAIN = "uncertain"
    NOT_APPLICABLE = "not_applicable"


class ViolationStatus(StrEnum):
    """Жизненный цикл нарушения."""

    OPEN = "open"
    CONFIRMED = "confirmed"
    FALSE_ALARM = "false_alarm"