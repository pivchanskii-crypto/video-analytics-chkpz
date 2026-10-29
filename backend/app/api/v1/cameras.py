"""Эндпоинты камер: /api/v1/cameras."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_camera_or_403, get_current_user, require_roles
from app.core.database import get_db
from app.models.camera import Camera
from app.models.user import User
from app.schemas.camera import CameraCreate, CameraRead, CameraUpdate
from app.services.access_service import assigned_camera_ids

router = APIRouter(prefix="/cameras", tags=["cameras"])


@router.get("", response_model=list[CameraRead], summary="Список камер")
def list_cameras(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Camera]:
    """Возвращает камеры: админу — все, оператору — только назначенные."""
    allowed = assigned_camera_ids(db, user)
    query = db.query(Camera)
    if allowed is not None:
        query = query.filter(Camera.id.in_(allowed))
    return query.order_by(Camera.id).all()


@router.post(
    "",
    response_model=CameraRead,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить камеру по RTSP",
)
def create_camera(
    body: CameraCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles("admin")),
) -> Camera:
    """Создаёт камеру. Доступно только администратору."""
    if db.query(Camera).filter(Camera.rtsp_url == body.rtsp_url).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Камера с таким rtsp_url уже существует",
        )

    camera = Camera(
        name=body.name,
        rtsp_url=body.rtsp_url,
        status=body.status,
        worker_id=body.worker_id,
        config=body.config,
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


@router.get("/{camera_id}", response_model=CameraRead, summary="Получить камеру")
def get_camera(camera: Camera = Depends(get_camera_or_403)) -> Camera:
    return camera


@router.patch("/{camera_id}", response_model=CameraRead, summary="Изменить камеру")
def update_camera(
    body: CameraUpdate,
    camera: Camera = Depends(get_camera_or_403),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles("admin")),
) -> Camera:
    """Частично обновляет камеру. Доступно только администратору."""
    data = body.model_dump(exclude_unset=True)

    new_rtsp = data.get("rtsp_url")
    if new_rtsp is not None and new_rtsp != camera.rtsp_url:
        exists = (
            db.query(Camera)
            .filter(Camera.rtsp_url == new_rtsp, Camera.id != camera.id)
            .first()
        )
        if exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Камера с таким rtsp_url уже существует",
            )

    for field, value in data.items():
        # Явный None пропускаем, кроме worker_id, где он означает «не назначен».
        if value is None and field != "worker_id":
            continue
        setattr(camera, field, value)

    db.commit()
    db.refresh(camera)
    return camera


@router.delete(
    "/{camera_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить камеру",
)
def delete_camera(
    camera: Camera = Depends(get_camera_or_403),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_roles("admin")),
) -> None:
    """Удаляет камеру (каскадно зоны и нарушения). Только администратор."""
    db.delete(camera)
    db.commit()