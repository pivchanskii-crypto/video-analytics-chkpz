"""Идемпотентный сидинг данных для локальной проверки сквозного пути.

Создаёт (если ещё нет) камеры с id из ``SEED_CAMERA_IDS`` и необязательного
администратора из ``SEED_ADMIN_LOGIN``/``SEED_ADMIN_PASSWORD``.

Камеры нужны, чтобы фоновый обработчик ``app.services.event_handler`` принимал
сообщения CV-воркера: события для несуществующих камер отклоняются. Без камер
нарушения не попадут в таблицу ``violations``.
"""
from __future__ import annotations

import logging
import os

from app.core.database import SessionLocal
from app.core.enums import UserRole
from app.core.security import hash_password
from app.models.camera import Camera
from app.models.user import User

logger = logging.getLogger(__name__)


def _camera_ids() -> list[int]:
    """Разбирает ``SEED_CAMERA_IDS`` (через запятую) в список целых id."""
    raw = os.getenv("SEED_CAMERA_IDS", "").strip()
    ids: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            logger.warning("Некорректный id камеры в SEED_CAMERA_IDS: %r", part)
    return ids


def seed() -> None:
    db = SessionLocal()
    try:
        for camera_id in _camera_ids():
            if db.get(Camera, camera_id) is None:
                db.add(
                    Camera(
                        id=camera_id,
                        name=f"Камера {camera_id}",
                        rtsp_url=f"synthetic://camera-{camera_id}",
                        status="online",
                        config={},
                    )
                )
                logger.info("Создана камера id=%s", camera_id)
            else:
                logger.info("Камера id=%s уже существует", camera_id)

        login = os.getenv("SEED_ADMIN_LOGIN", "").strip()
        if login:
            existing = db.query(User).filter(User.login == login).first()
            if existing is None:
                password = os.getenv("SEED_ADMIN_PASSWORD", "admin")
                email = os.getenv("SEED_ADMIN_EMAIL", "").strip() or None
                db.add(
                    User(
                        login=login,
                        email=email,
                        password_hash=hash_password(password),
                        role=UserRole.ADMIN,
                    )
                )
                logger.info("Создан администратор login=%s", login)
            else:
                logger.info("Администратор login=%s уже существует", login)

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    seed()