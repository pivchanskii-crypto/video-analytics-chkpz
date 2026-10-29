"""Перечисления предметной области CV-воркера.

Значения совпадают с классами/типами из ТЗ и сериализуются в JSON как обычные
строки (подкласс ``str``).
"""
from __future__ import annotations

import enum


class StrEnum(str, enum.Enum):
    """Базовый строковый enum — удобнее для JSON-сериализации и логов."""

    def __str__(self) -> str:
        return self.value


class DetectionClass(StrEnum):
    """Классы детекции (из ТЗ): человек и обязательные средства защиты."""

    PERSON = "person"
    HELMET = "helmet"  # каска
    SAFETY_VEST = "safety_vest"  # жилет


class ViolationType(StrEnum):
    """Тип события нарушения, отправляемого в очередь ``violations_queue``.

    Значения совпадают с ``app.core.enums.ViolationType`` бэкенда, чтобы воркер
    и бэкенд говорили на одном языке.
    """

    NO_PRE = "no_pre"  # отсутствие обязательных СИЗ (каска/жилет)
    ZONE_ENTRY = "zone_entry"  # вход в запрещённую зону
    UNAUTHORIZED = "unauthorized"  # несанкционированный доступ


# Обязательный набор классов детекции по ТЗ.
REQUIRED_DETECTION_CLASSES = [
    DetectionClass.PERSON,
    DetectionClass.HELMET,
    DetectionClass.SAFETY_VEST,
]