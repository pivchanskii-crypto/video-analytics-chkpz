"""Сервисный слой аутентификации.

Инкапсулирует бизнес-логику входа и выпуска/обновления токенов, отделяя её
от HTTP-слоя (роутеров).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models.user import User


class AuthError(Exception):
    """Ошибка аутентификации/авторизации."""


def _find_user_by_login(db: Session, login: str) -> User | None:
    """Возвращает пользователя по логину или ``None``."""
    return db.query(User).filter(User.login == login).first()


def authenticate(db: Session, login: str, password: str) -> User:
    """Проверяет учётные данные и возвращает пользователя.

    Поднимает :class:`AuthError` при неверном логине или пароле.
    """
    user = _find_user_by_login(db, login)
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("Неверный логин или пароль")
    return user


def _issue_token_pair(user: User) -> dict[str, Any]:
    """Выпускает пару access/refresh токенов для пользователя."""
    return {
        "access_token": create_access_token(user.id, user.role.value),
        "refresh_token": create_refresh_token(user.id, user.role.value),
        "token_type": "bearer",
        "access_expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "refresh_expires_in": settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
    }


def login(db: Session, login: str, password: str) -> dict[str, Any]:
    """Аутентифицирует пользователя и возвращает новую пару токенов."""
    user = authenticate(db, login, password)
    return _issue_token_pair(user)


def refresh(db: Session, refresh_token: str) -> dict[str, Any]:
    """Обменивает валидный refresh-токен на новую пару токенов."""
    try:
        payload = decode_token(refresh_token)
    except Exception as exc:  # noqa: BLE001 — любые ошибки PyJWT трактуем как невалидный токен
        raise AuthError("Недействительный refresh-токен") from exc

    if payload.get("type") != "refresh":
        raise AuthError("Передан не refresh-токен")

    user_id = payload.get("sub")
    if user_id is None:
        raise AuthError("Некорректный refresh-токен")

    user = db.get(User, int(user_id))
    if user is None:
        raise AuthError("Пользователь не найден")

    return _issue_token_pair(user)