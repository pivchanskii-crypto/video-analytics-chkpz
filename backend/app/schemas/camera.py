"""Pydantic-схемы эндпоинтов камер и зон."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import CheckType


def _validate_polygon_points(value: list[list[float]] | None) -> list[list[float]] | None:
    """Проверяет, что полигон валиден, а координаты лежат в ``[0, 1]``."""
    if value is None:
        return value
    if len(value) < 3:
        raise ValueError("Полигон должен содержать минимум 3 точки")
    for point in value:
        if len(point) != 2:
            raise ValueError("Каждая точка полигона должна быть парой [x, y]")
        x, y = point
        if not (0 <= x <= 1 and 0 <= y <= 1):
            raise ValueError("Координаты полигона должны находиться в диапазоне [0, 1]")
    return value


class CameraCreate(BaseModel):
    """Тело запроса на добавление камеры по RTSP."""

    name: str = Field(..., min_length=1, max_length=255)
    rtsp_url: str = Field(..., min_length=1, max_length=512)
    status: str = Field(default="offline", max_length=50)
    worker_id: int | None = None
    config: dict = Field(default_factory=dict)

    @field_validator("rtsp_url")
    @classmethod
    def _validate_rtsp_url(cls, value: str) -> str:
        if not (value.startswith("rtsp://") or value.startswith("rtsps://")):
            raise ValueError("rtsp_url должен начинаться с rtsp:// или rtsps://")
        return value


class CameraUpdate(BaseModel):
    """Тело запроса на частичное изменение камеры."""

    name: str | None = Field(None, min_length=1, max_length=255)
    rtsp_url: str | None = Field(None, min_length=1, max_length=512)
    status: str | None = Field(None, max_length=50)
    worker_id: int | None = None
    config: dict | None = None

    @field_validator("rtsp_url")
    @classmethod
    def _validate_rtsp_url(cls, value: str | None) -> str | None:
        if value is not None and not (
            value.startswith("rtsp://") or value.startswith("rtsps://")
        ):
            raise ValueError("rtsp_url должен начинаться с rtsp:// или rtsps://")
        return value


class CameraRead(BaseModel):
    """Камера в ответах API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    rtsp_url: str
    status: str
    worker_id: int | None
    config: dict


class ZoneCreate(BaseModel):
    """Тело запроса на создание зоны внутри кадра."""

    name: str = Field(..., min_length=1, max_length=255)
    polygon: list[list[float]] = Field(...)
    check_type: CheckType = CheckType.ZONE_ONLY
    active: bool = True

    @field_validator("polygon")
    @classmethod
    def _validate_polygon(cls, value: list[list[float]]) -> list[list[float]]:
        return _validate_polygon_points(value)


class ZoneUpdate(BaseModel):
    """Тело запроса на изменение зоны (в т.ч. смена типа проверки)."""

    name: str | None = Field(None, min_length=1, max_length=255)
    polygon: list[list[float]] | None = None
    check_type: CheckType | None = None
    active: bool | None = None

    @field_validator("polygon")
    @classmethod
    def _validate_polygon(cls, value: list[list[float]] | None) -> list[list[float]] | None:
        return _validate_polygon_points(value)


class ZoneRead(BaseModel):
    """Зона в ответах API."""

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    camera_id: int
    name: str
    polygon: list[list[float]]
    check_type: CheckType
    active: bool