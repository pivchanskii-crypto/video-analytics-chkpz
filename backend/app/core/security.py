"""Безопасность: хэширование паролей (bcrypt) и работа с JWT (PyJWT)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import settings


def hash_password(password: str) -> str:
    """Хэширует пароль через bcrypt и возвращает строковый хэш."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Проверяет соответствие пароля сохранённому хэшу."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except ValueError:
        # Некорректный формат хэша в БД — считаем пароль неверным.
        return False


def _create_token(
    user_id: int,
    role: str,
    token_type: str,
    expires_delta: timedelta,
) -> str:
    """Формирует JWT с общими для access/refresh полями."""
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: int, role: str) -> str:
    """Создаёт access-токен (срок жизни 1 час по ТЗ)."""
    return _create_token(
        user_id,
        role,
        "access",
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: int, role: str) -> str:
    """Создаёт refresh-токен (срок жизни 7 дней по ТЗ)."""
    return _create_token(
        user_id,
        role,
        "refresh",
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict[str, Any]:
    """Декодирует и проверяет JWT.

    При невалидном/истёкшем токене пробрасывает исключения ``jwt.PyJWTError``.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )