"""Вспомогательные SQLAlchemy-типы проекта.

Инкапсулирует соглашение о хранении перечислений: как ``VARCHAR`` со строковыми
значениями из ТЗ (``native_enum=False``) и маппингом значений через
``values_callable``. По умолчанию SQLAlchemy хранит *имена* членов enum
(``ADMIN``), а по ТЗ нужны значения (``admin``).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import Enum


def sa_enum(enum_cls: type[Any], name: str, length: int = 20) -> Enum:
    """Создаёт SQLAlchemy ``Enum``, хранящий строковые значения ``.value``.

    :param enum_cls: класс перечисления (подкласс ``StrEnum`` из ``app.core.enums``).
    :param name: имя типа enum (используется в метаданных/Alembic).
    :param length: размер итоговой VARCHAR-колонки.
    """
    return Enum(
        enum_cls,
        values_callable=lambda cls: [member.value for member in cls],
        native_enum=False,
        length=length,
        name=name,
    )