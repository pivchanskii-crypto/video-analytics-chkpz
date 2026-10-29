"""Управление WebSocket-подключениями и потоком нарушений.

WebSocket-эндпоинт регистрирует подключение с «областью видимости» (множество id
камер, назначенных оператору; ``None`` — администратор, все камеры). Новые
нарушения, приходящие из очереди Redis, рассылаются только тем операторам,
которым назначена камера нарушения.
"""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import WebSocket

from app.core.config import settings

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Хранит активные WebSocket-подключения и фильтрует рассылку по камерам."""

    def __init__(self) -> None:
        self._connections: dict[WebSocket, set[int] | None] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        websocket: WebSocket,
        allowed_camera_ids: set[int] | None,
    ) -> None:
        async with self._lock:
            self._connections[websocket] = allowed_camera_ids

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.pop(websocket, None)

    async def broadcast(self, camera_id: int, data: dict) -> None:
        """Рассылает нарушение операторам, которым назначена ``camera_id``."""
        async with self._lock:
            snapshot = list(self._connections.items())

        payload = {"type": "violation", "data": data}
        stale: list[WebSocket] = []
        for websocket, allowed in snapshot:
            if allowed is not None and camera_id not in allowed:
                continue
            try:
                await websocket.send_json(payload)
            except Exception:  # noqa: BLE001 — клиент мог отключиться
                stale.append(websocket)

        for websocket in stale:
            self.disconnect(websocket)


manager = ConnectionManager()


async def stream_redis_violations(stop_event: asyncio.Event) -> None:
    """Читает очередь Redis и рассылает новые нарушения по WebSocket.

    Подключение к Redis ленивое и необязательное: если пакет ``redis`` не
    установлен или сервер недоступен, слушатель просто не запускается, не
    блокируя работу HTTP-API.
    """
    try:
        import redis.asyncio as aioredis
    except ImportError:
        logger.warning("Пакет redis не установлен — трансляция нарушений отключена")
        return

    client = aioredis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        await client.ping()
    except Exception as exc:  # noqa: BLE001 — любая ошибка сокета = нет связи
        logger.warning("Redis недоступен (%s) — трансляция нарушений отключена", exc)
        await client.aclose()
        return

    logger.info("Слушатель очереди «%s» запущен", settings.VIOLATIONS_QUEUE)
    try:
        while not stop_event.is_set():
            try:
                item = await client.blpop(settings.VIOLATIONS_QUEUE, timeout=1)
            except Exception as exc:  # noqa: BLE001 — сетевые сбои не должны ронять задачу
                logger.error("Ошибка чтения очереди Redis: %s", exc)
                await asyncio.sleep(1)
                continue

            if item is None:
                continue

            _, raw_message = item
            try:
                data = json.loads(raw_message)
                camera_id = int(data.get("camera_id", 0))
            except (TypeError, ValueError) as exc:
                logger.warning(
                    "Некорректное сообщение в очереди «%s»: %s",
                    settings.VIOLATIONS_QUEUE,
                    exc,
                )
                continue

            data["camera_id"] = camera_id
            await manager.broadcast(camera_id, data)
    finally:
        try:
            await client.aclose()
        except Exception:  # noqa: BLE001
            pass