"""Pydantic-схемы данных воркера: детекция и событие нарушения."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from worker.core.enums import DetectionClass, ViolationType


class Detection(BaseModel):
    """Один обнаруженный на кадре объект."""

    track_id: str | None = None
    class_name: DetectionClass
    # Координаты bbox (нормализованные или в пикселях); в фазе 3 — заглушка.
    bbox: list[float] | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    # Атрибуты объекта: наличие каски, жилета и т.п.
    attributes: dict[str, Any] = Field(default_factory=dict)


class ViolationEvent(BaseModel):
    """Сообщение о нарушении, публикуемое в очередь Redis.

    Структура (из ТЗ): ``camera_id``, ``track_id``, ``type``, ``timestamp``.
    """

    camera_id: str
    track_id: str
    type: ViolationType
    timestamp: str
    frame_path: str | None = None

    @classmethod
    def create(
        cls,
        *,
        camera_id: str,
        track_id: str,
        violation_type: ViolationType,
        timestamp: datetime | None = None,
    ) -> "ViolationEvent":
        """Создаёт событие с временной меткой в ISO 8601 (UTC)."""
        ts = timestamp or datetime.now(timezone.utc)
        return cls(
            camera_id=camera_id,
            track_id=track_id,
            type=violation_type,
            timestamp=ts.isoformat(),
        )

    def to_json(self) -> str:
        """Сериализует событие в JSON-строку для отправки в очередь.

        ``frame_path`` включается в сообщение только когда задан — ``None``
        не отправляется в очередь.
        """
        return self.model_dump_json(exclude_none=True)