"""Заглушка модуля детекции (:class:`MockModule`).

Имитирует работу CV-модуля без реальной нейросети (Ultralytics): раз в секунду
генерирует фейкового человека без обязательных СИЗ (``no_pre``) и возвращает
соответствующее событие.
"""
from __future__ import annotations

import itertools
import random
import time
from typing import Any

from worker.core.enums import DetectionClass, ViolationType
from worker.core.schemas import Detection, ViolationEvent
from worker.modules.base import DetectionModule


class MockModule(DetectionModule):
    """Генерирует фейковое событие «человек без СИЗ» (``no_pre``).

    Реальная детекция не выполняется: :meth:`detect` возвращает одного человека
    с атрибутом ``helmet=False`` и постоянным ``track_id`` в течение
    ``track_lifetime_seconds``, а :meth:`check_violation` — событие нарушения не
    чаще одного раза в секунду. Постоянный ``track_id`` нужен, чтобы бэкенд
    (дедупликация + порог «в зоне дольше N секунд») подтвердил нарушение.
    """

    def __init__(
        self,
        camera_id: str,
        min_interval_seconds: float = 1.0,
        track_lifetime_seconds: float = 10.0,
    ) -> None:
        self._camera_id = camera_id
        self._min_interval_seconds = min_interval_seconds
        self._track_lifetime_seconds = max(1.0, float(track_lifetime_seconds))
        self._last_emit_at = 0.0
        self._track_ids = itertools.count(1)
        self._current_track_id = str(next(self._track_ids))
        self._track_started_at = time.monotonic()

    @property
    def name(self) -> str:
        return DetectionClass.PERSON.value

    def detect(self, frame: Any) -> list[Detection]:
        # Держим постоянный track_id в течение track_lifetime_seconds, чтобы
        # бэкенд подтвердил нарушение. По истечении срока выдаём нового
        # «человека» с новым track_id (имитация ухода/прихода).
        now = time.monotonic()
        if now - self._track_started_at >= self._track_lifetime_seconds:
            self._current_track_id = str(next(self._track_ids))
            self._track_started_at = now

        return [
            Detection(
                track_id=self._current_track_id,
                class_name=DetectionClass.PERSON,
                confidence=round(random.uniform(0.85, 0.99), 4),
                attributes={"helmet": False, "safety_vest": False},
            )
        ]

    def check_violation(
        self,
        detections: list[Detection],
        config: dict[str, Any],
    ) -> list[ViolationEvent]:
        # Дополнительная защита от избыточной отправки: не чаще 1 события/сек.
        now = time.monotonic()
        if now - self._last_emit_at < self._min_interval_seconds:
            return []

        for detection in detections:
            if (
                detection.class_name == DetectionClass.PERSON
                and not detection.attributes.get("helmet", True)
            ):
                self._last_emit_at = now
                return [
                    ViolationEvent.create(
                        camera_id=self._camera_id,
                        track_id=detection.track_id or "unknown",
                        violation_type=ViolationType.NO_PRE,
                    )
                ]
        return []