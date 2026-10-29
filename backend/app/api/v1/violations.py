"""Эндпоинты нарушений: /api/v1/violations."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from app.api.deps import ensure_camera_access, get_current_user
from app.core.database import get_db
from app.core.enums import ViolationStatus, ViolationType
from app.models.user import User
from app.models.violation import Violation
from app.models.zone import Zone
from app.schemas.violation import (
    FeedbackRequest,
    ViolationListResponse,
    ViolationRead,
)
from app.services import violation_service
from app.services.access_service import assigned_camera_ids

router = APIRouter(prefix="/violations", tags=["violations"])


@router.get("", response_model=ViolationListResponse, summary="Лента нарушений")
def list_violations(
    camera_id: int | None = None,
    zone_id: int | None = None,
    type_: ViolationType | None = Query(None, alias="type"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    include_admitted: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ViolationListResponse:
    """Возвращает нарушения с фильтрами.

    «Допущенные» нарушения (лицо идентифицировано и имеет разрешение на зону)
    по умолчанию скрываются. Оператор видит только нарушения своих камер.
    """
    allowed_ids = assigned_camera_ids(db, user)

    if camera_id is not None:
        ensure_camera_access(db, user, camera_id)

    if zone_id is not None:
        zone = db.get(Zone, zone_id)
        if zone is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Зона не найдена")
        ensure_camera_access(db, user, zone.camera_id)
        if camera_id is not None and zone.camera_id != camera_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Зона не относится к указанной камере",
            )

    items, total = violation_service.list_violations(
        db,
        allowed_camera_ids=allowed_ids,
        camera_id=camera_id,
        zone_id=zone_id,
        type_=type_,
        date_from=date_from,
        date_to=date_to,
        include_admitted=include_admitted,
        limit=limit,
        offset=offset,
    )

    permitted = violation_service.admitted_pairs(db, items)
    payload = [
        ViolationRead(
            **violation_service.serialize_violation(
                violation,
                (violation.zone_id, violation.face_id) in permitted,
            )
        )
        for violation in items
    ]
    return ViolationListResponse(items=payload, total=total, limit=limit, offset=offset)


@router.post(
    "/{violation_id}/feedback",
    response_model=ViolationRead,
    summary="Обратная связь по нарушению",
)
def send_feedback(
    violation_id: int,
    body: FeedbackRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ViolationRead:
    """Подтверждает нарушение или помечает его ложной тревогой."""
    violation = (
        db.query(Violation)
        .options(
            selectinload(Violation.camera),
            selectinload(Violation.zone),
            selectinload(Violation.face),
        )
        .filter(Violation.id == violation_id)
        .first()
    )

    if violation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Нарушение не найдено")

    allowed_ids = assigned_camera_ids(db, user)
    if allowed_ids is not None and violation.camera_id not in allowed_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ к нарушению запрещён",
        )

    if violation.status != ViolationStatus.OPEN:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Нарушение уже обработано",
        )

    violation.status = ViolationStatus(body.decision)
    db.commit()
    db.refresh(violation)

    admitted = violation_service.is_violation_admitted(db, violation)
    return ViolationRead(**violation_service.serialize_violation(violation, admitted))