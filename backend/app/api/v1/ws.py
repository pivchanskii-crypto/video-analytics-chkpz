"""WebSocket-эндпоинт трансляции нарушений: /api/v1/ws/violations."""
from __future__ import annotations

from fastapi import APIRouter, WebSocket
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.core.database import SessionLocal
from app.core.security import decode_token
from app.models.user import User
from app.services.access_service import assigned_camera_ids
from app.services.ws_manager import manager

router = APIRouter()


def _authenticate(db: Session, token: str) -> User:
    """Декодирует access-токен и возвращает пользователя."""
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise ValueError("Передан не access-токен")
    user_id = payload.get("sub")
    if user_id is None:
        raise ValueError("Некорректный токен")

    user = db.get(User, int(user_id))
    if user is None:
        raise ValueError("Пользователь не найден")
    return user


@router.websocket("/ws/violations")
async def ws_violations(websocket: WebSocket) -> None:
    """Поток новых нарушений с проверкой JWT и фильтром по камерам оператора.

    Токен передаётся либо в query-параметре ``?token=...``, либо в заголовке
    ``Authorization: Bearer ...``.
    """
    await websocket.accept()

    token = websocket.query_params.get("token")
    authorization = websocket.headers.get("authorization")
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()

    if not token:
        await websocket.close(code=1008)
        return

    db = SessionLocal()
    try:
        try:
            user = _authenticate(db, token)
        except Exception:  # noqa: BLE001 — невалидный токен
            await websocket.close(code=1008)
            return
        allowed_camera_ids = assigned_camera_ids(db, user)
    finally:
        db.close()

    await manager.connect(websocket, allowed_camera_ids)
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)