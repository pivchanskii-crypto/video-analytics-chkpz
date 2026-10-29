"""Pydantic-схемы эндпоинтов аутентификации."""
from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Тело запроса на вход."""

    login: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1)


class RefreshRequest(BaseModel):
    """Тело запроса на обновление токенов."""

    refresh_token: str = Field(..., min_length=1)


class TokenPair(BaseModel):
    """Пара токенов, возвращаемая клиенту."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    access_expires_in: int
    refresh_expires_in: int