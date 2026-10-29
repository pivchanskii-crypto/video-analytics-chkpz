"""Эндпоинты аутентификации: /api/v1/auth/*."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.auth import LoginRequest, RefreshRequest, TokenPair
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair, summary="Вход по логину и паролю")
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenPair:
    """Аутентифицирует пользователя и выдаёт пару access/refresh токенов."""
    try:
        tokens = auth_service.login(db, body.login, body.password)
    except auth_service.AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    return TokenPair(**tokens)


@router.post("/refresh", response_model=TokenPair, summary="Обновление токенов")
def refresh(body: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    """Обменивает refresh-токен на новую пару access/refresh токенов."""
    try:
        tokens = auth_service.refresh(db, body.refresh_token)
    except auth_service.AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    return TokenPair(**tokens)