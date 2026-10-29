"""Pydantic-схемы эндпоинтов нарушений."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    """Решение оператора по нарушению (кнопки «Подтвердить» / «Ложная тревога»)."""

    decision: Literal["confirmed", "false_alarm"] = Field(
        ...,
        description="confirmed — Подтвердить, false_alarm — Ложная тревога",
    )


class ViolationRead(BaseModel):
    """Нарушение в ответах API."""

    id: int
    camera_id: int
    zone_id: int | None
    track_id: str | None
    type: str
    timestamp: datetime
    frame_path: str | None
    frame_url: str | None = None
    face_id: int | None
    identity_status: str
    status: str
    admitted: bool
    camera_name: str | None = None
    zone_name: str | None = None


class ViolationListResponse(BaseModel):
    """Страница ленты нарушений."""

    items: list[ViolationRead]
    total: int
    limit: int
    offset: int