"""Обработка событий нарушений из очереди Redis (Фаза 5).

Слушает очередь ``violations_queue``, куда CV-воркер публикует события,
дедуплицирует их по ключу (камера, зона, тип, track_id), применяет проверку
минимального времени нахождения в зоне и при подтверждённом нарушении создаёт
запись в БД и рассылает Email-оповещения назначенным операторам.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import app_config, settings
from app.core.database import SessionLocal
from app.core.enums import UserRole, ViolationType
from app.models.alert import Alert
from app.models.camera import Camera
from app.models.operator_camera import OperatorCamera
from app.models.user import User
from app.models.violation import Violation
from app.models.zone import Zone
from app.services import notification_service
from app.services.violation_service import build_frame_url
from app.services.ws_manager import manager

logger = logging.getLogger(__name__)

# Значения по умолчанию, если соответствующие ключи не заданы в config.yaml.
DEFAULT_ZONE_STAY_SECONDS = 3
DEFAULT_PRESENCE_TTL_SECONDS = 30


def _threshold_int(name: str, default: int) -> int:
    """Возвращает целочисленный порог из ``config.yaml`` с fallback."""
    value = app_config.thresholds.get(name, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_event_message(raw_message: str) -> dict[str, Any] | None:
    """Разбирает JSON-сообщение воркера и возвращает нормализованное событие.

    Возвращает ``None``, если сообщение некорректно (невалидный JSON, тип
    нарушения, ``camera_id`` и т.д.). ``zone_id`` опционален: воркер передаёт
    его, когда трек сопоставлен с зоной; иначе ``None``.
    """
    try:
        data = json.loads(raw_message)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("Некорректный JSON в очереди: %s", exc)
        return None

    if not isinstance(data, dict):
        logger.warning("Сообщение не является объектом JSON: %r", data)
        return None

    try:
        camera_id = int(data.get("camera_id"))
    except (TypeError, ValueError) as exc:
        logger.warning("Некорректный camera_id %r: %s", data.get("camera_id"), exc)
        return None

    zone_id: int | None = None
    raw_zone_id = data.get("zone_id")
    if raw_zone_id is not None:
        try:
            zone_id = int(raw_zone_id)
        except (TypeError, ValueError):
            logger.warning("Некорректный zone_id %r — игнорируем", raw_zone_id)
            zone_id = None

    track_id = str(data.get("track_id") or "").strip() or "unknown"

    try:
        violation_type = ViolationType(data["type"])
    except (KeyError, ValueError) as exc:
        logger.warning("Неизвестный тип нарушения %r: %s", data.get("type"), exc)
        return None

    timestamp = _parse_timestamp(data.get("timestamp"))
    frame_path = data.get("frame_path") or data.get("frame_url") or None
    if not isinstance(frame_path, str):
        frame_path = None

    return {
        "camera_id": camera_id,
        "zone_id": zone_id,
        "track_id": track_id,
        "type": violation_type,
        "timestamp": timestamp,
        "frame_path": frame_path,
    }


def _parse_timestamp(raw: Any) -> datetime:
    """Преобразует timestamp события в ``datetime`` (UTC), иначе — текущее время."""
    if isinstance(raw, str):
        try:
            value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value
        except ValueError:
            logger.warning("Некорректный timestamp %r — используем текущее время", raw)
    return datetime.now(timezone.utc)


class DedupGate:
    """Дедупликация событий и гейт «человек в зоне дольше N секунд».

    Ключом события служит ``(camera_id, zone_id, type, track_id)``. Первое
    появление ключа регистрируется, но событие не создаётся. Нарушение
    создаётся только тогда, когда ключ непрерывно присутствует дольше
    ``stay_seconds``. Пока человек не покинул зону/кадр (ключ «жив»), повторная
    запись не создаётся; ключ считается «ушедшим» после ``ttl_seconds`` без
    событий.
    """

    def __init__(self, stay_seconds: float, ttl_seconds: float) -> None:
        self.stay_seconds = max(0.0, float(stay_seconds))
        self.ttl_seconds = max(0.0, float(ttl_seconds))
        self._first_seen: dict[tuple[Any, ...], float] = {}
        self._last_seen: dict[tuple[Any, ...], float] = {}
        self._emitted: set[tuple[Any, ...]] = set()
        self._lock = threading.Lock()

    def _purge(self, now: float) -> None:
        if self.ttl_seconds <= 0:
            return
        expired = [
            key
            for key, last_seen in self._last_seen.items()
            if now - last_seen > self.ttl_seconds
        ]
        for key in expired:
            self._first_seen.pop(key, None)
            self._last_seen.pop(key, None)
            self._emitted.discard(key)

    def observe(self, key: tuple[Any, ...], now: float) -> bool:
        """Регистрирует появление ключа и сообщает, пора ли создавать событие."""
        with self._lock:
            self._purge(now)
            if key in self._emitted:
                self._last_seen[key] = now
                return False
            if key not in self._first_seen:
                self._first_seen[key] = now
                self._last_seen[key] = now
                return False
            self._last_seen[key] = now
            return (now - self._first_seen[key]) >= self.stay_seconds

    def mark_emitted(self, key: tuple[Any, ...]) -> None:
        """Помечает ключ как уже созданный (дедупликация до ухода из зоны)."""
        with self._lock:
            self._emitted.add(key)

    def reset(self, key: tuple[Any, ...]) -> None:
        """Сбрасывает состояние ключа (например, после ошибки сохранения)."""
        with self._lock:
            self._first_seen.pop(key, None)
            self._last_seen.pop(key, None)
            self._emitted.discard(key)


class EventProcessor:
    """Объединяет разбор, дедупликацию, сохранение и оповещение по событиям."""

    def __init__(
        self,
        *,
        db_factory=SessionLocal,
        zone_stay_seconds: int | None = None,
        presence_ttl_seconds: int | None = None,
        delivery_timeout_seconds: int | None = None,
    ) -> None:
        self._db_factory = db_factory
        self._gate = DedupGate(
            stay_seconds=(
                zone_stay_seconds
                if zone_stay_seconds is not None
                else _threshold_int("zone_stay_seconds", DEFAULT_ZONE_STAY_SECONDS)
            ),
            ttl_seconds=(
                presence_ttl_seconds
                if presence_ttl_seconds is not None
                else _threshold_int("presence_ttl_seconds", DEFAULT_PRESENCE_TTL_SECONDS)
            ),
        )
        self._delivery_timeout = (
            delivery_timeout_seconds
            if delivery_timeout_seconds is not None
            else settings.ALERT_DELIVERY_TIMEOUT_SECONDS
        )

    def process(self, raw_message: str) -> dict[str, Any] | None:
        """Обрабатывает одно сообщение очереди.

        Возвращает словарь нового нарушения для WebSocket-трансляции либо
        ``None``, если событие отфильтровано, дедуплицировано или ещё не
        подтверждено по времени нахождения в зоне.
        """
        event = parse_event_message(raw_message)
        if event is None:
            return None

        key = (
            event["camera_id"],
            event["zone_id"],
            event["type"].value,
            event["track_id"],
        )
        if not self._gate.observe(key, time.monotonic()):
            return None

        db = self._db_factory()
        try:
            return self._process_event(db, event, key)
        finally:
            db.close()

    def _process_event(
        self,
        db: Session,
        event: dict[str, Any],
        key: tuple[Any, ...],
    ) -> dict[str, Any] | None:
        if not self._location_valid(db, event["camera_id"], event["zone_id"]):
            return None

        violation = Violation(
            camera_id=event["camera_id"],
            zone_id=event["zone_id"],
            track_id=event["track_id"],
            type=event["type"],
            timestamp=event["timestamp"],
            frame_path=event["frame_path"],
        )
        db.add(violation)
        db.flush()

        recipients = self._operator_recipients(db, event["camera_id"])
        alerts = [
            Alert(
                violation_id=violation.id,
                channel="email",
                recipient=recipient,
                status="pending",
            )
            for recipient in recipients
        ]
        if alerts:
            db.add_all(alerts)

        try:
            db.commit()
        except Exception:  # noqa: BLE001 — не теряем событие: сбросим гейт и вернём None
            db.rollback()
            self._gate.reset(key)
            logger.exception("Не удалось сохранить нарушение для события %s", key)
            return None

        self._gate.mark_emitted(key)

        try:
            self._deliver_alerts(db, violation, alerts)
        except Exception:  # noqa: BLE001 — нарушение уже сохранено; не роняем обработчик
            db.rollback()
            logger.exception(
                "Ошибка при рассылке оповещений по нарушению %s",
                violation.id,
            )

        return self._serialize(violation)

    def _location_valid(self, db: Session, camera_id: int, zone_id: int | None) -> bool:
        camera = db.get(Camera, camera_id)
        if camera is None:
            logger.warning("Камера %s не найдена — событие отклонено", camera_id)
            return False
        if zone_id is not None:
            zone = db.get(Zone, zone_id)
            if zone is None or zone.camera_id != camera_id:
                logger.warning(
                    "Зона %s не относится к камере %s — событие отклонено",
                    zone_id,
                    camera_id,
                )
                return False
        return True

    def _operator_recipients(self, db: Session, camera_id: int) -> list[str]:
        """Возвращает адреса операторов, назначенных на камеру."""
        rows = (
            db.query(User.email, User.login)
            .join(OperatorCamera, OperatorCamera.operator_id == User.id)
            .filter(
                OperatorCamera.camera_id == camera_id,
                User.role == UserRole.OPERATOR,
            )
            .all()
        )
        recipients = [email or login for email, login in rows]
        # Сохраняем порядок и убираем повторы.
        return list(dict.fromkeys(recipients))

    def _deliver_alerts(
        self,
        db: Session,
        violation: Violation,
        alerts: list[Alert],
    ) -> None:
        if not alerts:
            logger.info(
                "По нарушению %s нет назначенных операторов — оповещения пропущены",
                violation.id,
            )
            return

        subject = f"Нарушение «{violation.type.value}» (камера {violation.camera_id})"
        body = self._compose_body(violation)

        for alert in alerts:
            try:
                notification_service.send_email_with_deadline(
                    to=alert.recipient,
                    subject=subject,
                    body=body,
                    frame_path=violation.frame_path,
                    deadline_seconds=self._delivery_timeout,
                )
            except notification_service.NotificationError as exc:
                logger.error(
                    "Оповещение %s по нарушению %s не доставлено: %s",
                    alert.recipient,
                    violation.id,
                    exc,
                )
                alert.status = "failed"
                alert.sent_at = None
            else:
                alert.status = "sent"
                alert.sent_at = datetime.now(timezone.utc)

        db.commit()

    def _compose_body(self, violation: Violation) -> str:
        lines = [
            "Зафиксировано новое нарушение:",
            f"  Тип: {violation.type.value}",
            f"  Камера: {violation.camera_id}",
            f"  Зона: {violation.zone_id if violation.zone_id is not None else '-'}",
            f"  Track: {violation.track_id}",
            f"  Время: {violation.timestamp.isoformat()}",
        ]
        if violation.frame_path:
            lines.append(f"  Кадр: {violation.frame_path}")
        return "\n".join(lines)

    def _serialize(self, violation: Violation) -> dict[str, Any]:
        return {
            "id": violation.id,
            "camera_id": violation.camera_id,
            "zone_id": violation.zone_id,
            "track_id": violation.track_id,
            "type": violation.type.value,
            "timestamp": violation.timestamp.isoformat(),
            "frame_path": violation.frame_path,
            "frame_url": build_frame_url(violation.frame_path),
            "face_id": violation.face_id,
            "identity_status": violation.identity_status.value,
            "status": violation.status.value,
        }
async def run_event_consumer(stop_event: asyncio.Event) -> None:
    """Слушает очередь Redis и обрабатывает сообщения воркера.

    Redis подключается лениво: если пакет ``redis`` не установлен или сервер
    недоступен, обработка просто не запускается, не блокируя HTTP-API.
    """
    try:
        import redis.asyncio as aioredis
    except ImportError:
        logger.warning("Пакет redis не установлен — обработка событий отключена")
        return

    client = aioredis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        await client.ping()
    except Exception as exc:  # noqa: BLE001 — любая ошибка сокета = нет связи
        logger.warning("Redis недоступен (%s) — обработка событий отключена", exc)
        await client.aclose()
        return

    processor = EventProcessor()
    logger.info("Обработчик очереди «%s» запущен", settings.VIOLATIONS_QUEUE)
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
                payload = await asyncio.to_thread(processor.process, raw_message)
            except Exception:  # noqa: BLE001
                logger.exception("Неожиданная ошибка обработки сообщения")
                continue

            if payload is not None:
                await manager.broadcast(payload["camera_id"], payload)
    finally:
        try:
            await client.aclose()
        except Exception:  # noqa: BLE001
            pass