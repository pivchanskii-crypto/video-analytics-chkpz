"""Общие FastAPI-зависимости.

``get_db`` объявлена в :mod:`app.core.database`; здесь — аутентификация по
access-токену и проверка ролей.
"""
from __future__ import annotations

from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, Path, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models.camera import Camera
from app.models.user import User
from app.services.access_service import assigned_camera_ids

# Bearer-схема без автоматического исключения: детали ошибки формируем сами.
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Извлекает текущего пользователя из access-токена.

    Возвращает :class:`User` либо поднимает ``401`` при отсутствии/невалидности
    токена или отсутствии пользователя в БД.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не авторизован",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный токен",
        ) from exc

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Передан не access-токен",
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректный токен",
        )

    user = db.get(User, int(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден",
        )
    return user


def require_roles(*allowed_roles: str) -> Callable:
    """Фабрика зависимостей: разрешает доступ только указанным ролям.

    Пример:
        ``Depends(require_roles("admin"))`` — только администратор;
        ``Depends(require_roles("admin", "operator"))`` — обе роли.

    Возвращает зависимость, которая проверяет роль текущего пользователя
    и поднимает ``403`` при недостатке прав.
    """

    def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role.value not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав",
            )
        return user

    return role_checker


def ensure_camera_access(db: Session, user: User, camera_id: int) -> Camera:
    """Проверяет доступ пользователя к камере и возвращает её.

    Администратору доступны все камеры. Оператору — только те, что перечислены
    в ``operator_camera``; иначе ``403``. Несуществующая камера — ``404``.
    """
    camera = db.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Камера не найдена",
        )

    allowed = assigned_camera_ids(db, user)
    if allowed is not None and camera.id not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ к камере запрещён",
        )
    return camera


def get_camera_or_403(
    camera_id: int = Path(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Camera:
    """FastAPI-зависимость: камера с проверкой доступа по роли оператора."""
    return ensure_camera_access(db, user, camera_id)