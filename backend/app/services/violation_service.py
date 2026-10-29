"""Сервисный слой нарушений: фильтрация и сериализация."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy import and_, exists, select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import IdentityStatus, ViolationType
from app.models.violation import Violation
from app.models.zone_permission import ZonePermission

# URL-префикс, под которым в ``main.py`` смонтирована статическая раздача кадров.
FRAMES_URL_PREFIX = "/api/v1/frames"


def build_frame_url(frame_path: str | None) -> str | None:
    """Формирует публичный URL кадра из ``frame_path``.

    Локальный путь ``/app/frames/123.jpg`` превращается в
    ``/api/v1/frames/123.jpg``. Внешние http(s)-ссылки возвращаются без
    изменений, ``None`` — без изменений.
    """
    if not frame_path:
        return None
    if frame_path.startswith(("http://", "https://")):
        return frame_path
    filename = Path(frame_path).name
    if not filename:
        return None
    return f"{FRAMES_URL_PREFIX}/{filename}"


def _admitted_condition():
    """SQL-условие «нарушение допущено».

    «Допущенным» считается нарушение, у которого лицо идентифицировано
    (``identity_status == identified``) и у этого лица есть разрешение на зону
    (запись в ``zone_permissions``). Такие записи по умолчанию скрываются из ленты.
    """
    permission_exists = exists(
        select(ZonePermission.zone_id).where(
            ZonePermission.zone_id == Violation.zone_id,
            ZonePermission.face_id == Violation.face_id,
        )
    )
    return and_(
        Violation.identity_status == IdentityStatus.IDENTIFIED,
        permission_exists,
    )


def list_violations(
    db: Session,
    *,
    allowed_camera_ids: set[int] | None,
    camera_id: int | None = None,
    zone_id: int | None = None,
    type_: ViolationType | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    include_admitted: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Violation], int]:
    """Возвращает страницу нарушений с учётом области видимости и фильтров.

    :return: кортеж ``(элементы, общее_число_записей)``.
    """
    query = db.query(Violation).options(
        selectinload(Violation.camera),
        selectinload(Violation.zone),
        selectinload(Violation.face),
    )

    if allowed_camera_ids is not None:
        query = query.filter(Violation.camera_id.in_(allowed_camera_ids))
    if camera_id is not None:
        query = query.filter(Violation.camera_id == camera_id)
    if zone_id is not None:
        query = query.filter(Violation.zone_id == zone_id)
    if type_ is not None:
        query = query.filter(Violation.type == type_)
    if date_from is not None:
        query = query.filter(Violation.timestamp >= date_from)
    if date_to is not None:
        query = query.filter(Violation.timestamp <= date_to)
    if not include_admitted:
        query = query.filter(~_admitted_condition())

    total = query.count()
    items = (
        query.order_by(Violation.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return items, total


def admitted_pairs(db: Session, violations: list[Violation]) -> set[tuple[int, int]]:
    """Возвращает множество пар ``(zone_id, face_id)``, имеющих разрешение.

    Пары собираются одним SQL-запросом, чтобы не делать N+1 запрос при
    сериализации страницы нарушений.
    """
    candidate_pairs = {
        (violation.zone_id, violation.face_id)
        for violation in violations
        if violation.identity_status == IdentityStatus.IDENTIFIED
        and violation.zone_id is not None
        and violation.face_id is not None
    }
    if not candidate_pairs:
        return set()

    zone_ids = {zone_id for zone_id, _ in candidate_pairs}
    face_ids = {face_id for _, face_id in candidate_pairs}
    rows = (
        db.query(ZonePermission.zone_id, ZonePermission.face_id)
        .filter(
            ZonePermission.zone_id.in_(zone_ids),
            ZonePermission.face_id.in_(face_ids),
        )
        .all()
    )
    return {(zone_id, face_id) for zone_id, face_id in rows}


def is_violation_admitted(db: Session, violation: Violation) -> bool:
    """Определяет, является ли конкретное нарушение «допущенным»."""
    if violation.identity_status != IdentityStatus.IDENTIFIED:
        return False
    if violation.zone_id is None or violation.face_id is None:
        return False
    return (
        db.query(ZonePermission.zone_id)
        .filter(
            ZonePermission.zone_id == violation.zone_id,
            ZonePermission.face_id == violation.face_id,
        )
        .first()
        is not None
    )


def serialize_violation(violation: Violation, admitted: bool) -> dict:
    """Сериализует ORM-нарушение в словарь для :class:`ViolationRead`."""
    camera = violation.camera
    zone = violation.zone
    return {
        "id": violation.id,
        "camera_id": violation.camera_id,
        "zone_id": violation.zone_id,
        "track_id": violation.track_id,
        "type": violation.type.value,
        "timestamp": violation.timestamp,
        "frame_path": violation.frame_path,
        "frame_url": build_frame_url(violation.frame_path),
        "face_id": violation.face_id,
        "identity_status": violation.identity_status.value,
        "status": violation.status.value,
        "admitted": admitted,
        "camera_name": camera.name if camera else None,
        "zone_name": zone.name if zone else None,
    }