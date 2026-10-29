"""Эндпоинты зон камеры: /api/v1/cameras/{camera_id}/zones."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_camera_or_403, require_roles
from app.core.database import get_db
from app.models.camera import Camera
from app.models.user import User
from app.models.zone import Zone
from app.schemas.camera import ZoneCreate, ZoneRead, ZoneUpdate

router = APIRouter(prefix="/cameras/{camera_id}/zones", tags=["zones"])


def _get_zone_or_404(db: Session, camera_id: int, zone_id: int) -> Zone:
    zone = db.get(Zone, zone_id)
    if zone is None or zone.camera_id != camera_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Зона не найдена")
    return zone


@router.get("", response_model=list[ZoneRead], summary="Список зон камеры")
def list_zones(
    camera: Camera = Depends(get_camera_or_403),
    db: Session = Depends(get_db),
) -> list[Zone]:
    return db.query(Zone).filter(Zone.camera_id == camera.id).order_by(Zone.id).all()


@router.post(
    "",
    response_model=ZoneRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать зону",
)
def create_zone(
    body: ZoneCreate,
    camera: Camera = Depends(get_camera_or_403),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles("admin")),
) -> Zone:
    """Создаёт зону-полигон. Доступно только администратору."""
    zone = Zone(
        camera_id=camera.id,
        name=body.name,
        polygon=body.polygon,
        check_type=body.check_type,
        active=body.active,
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone


@router.get("/{zone_id}", response_model=ZoneRead, summary="Получить зону")
def get_zone(
    zone_id: int,
    camera: Camera = Depends(get_camera_or_403),
    db: Session = Depends(get_db),
) -> Zone:
    return _get_zone_or_404(db, camera.id, zone_id)


@router.patch("/{zone_id}", response_model=ZoneRead, summary="Изменить зону")
def update_zone(
    zone_id: int,
    body: ZoneUpdate,
    camera: Camera = Depends(get_camera_or_403),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles("admin")),
) -> Zone:
    """Изменяет зону (в т.ч. тип проверки). Доступно только администратору."""
    zone = _get_zone_or_404(db, camera.id, zone_id)
    data = body.model_dump(exclude_unset=True)
    for field, value in data.items():
        if value is None:
            continue
        setattr(zone, field, value)

    db.commit()
    db.refresh(zone)
    return zone


@router.delete(
    "/{zone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить зону",
)
def delete_zone(
    zone_id: int,
    camera: Camera = Depends(get_camera_or_403),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles("admin")),
) -> None:
    """Удаляет зону. Доступно только администратору."""
    zone = _get_zone_or_404(db, camera.id, zone_id)
    db.delete(zone)
    db.commit()