"""Точка входа FastAPI-приложения."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1 import auth, cameras, violations, ws, zones
from app.core.config import app_config, settings
from app.services.event_handler import run_event_consumer

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Запускает фоновую обработку очереди нарушений на время жизни приложения."""
    stop_event = asyncio.Event()
    consumer_task = asyncio.create_task(run_event_consumer(stop_event))

    yield

    stop_event.set()
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Video Surveillance Platform",
    version=app_config.app.get("version", "0.1.0"),
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_config.cors.get("allowed_origins", []),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(cameras.router, prefix="/api/v1")
app.include_router(zones.router, prefix="/api/v1")
app.include_router(violations.router, prefix="/api/v1")
app.include_router(ws.router, prefix="/api/v1")

# Статическая раздача кадров нарушений: /api/v1/frames/{filename}.
# Создаём каталог, если его ещё нет (в контейнере это /app/frames). Если
# каталог недоступен (например, вне контейнера без прав на запись), —
# приложение продолжает работать, но раздача кадров не монтируется.
frames_dir = Path(settings.FRAMES_DIR)
try:
    frames_dir.mkdir(parents=True, exist_ok=True)
except OSError as exc:
    logger.warning(
        "Каталог кадров %s недоступен — статическая раздача не смонтирована: %s",
        frames_dir,
        exc,
    )
else:
    app.mount(
        "/api/v1/frames",
        StaticFiles(directory=str(frames_dir)),
        name="frames",
    )


@app.get("/health", tags=["system"], summary="Проверка живости сервиса")
def health() -> dict[str, str]:
    """Возвращает статус сервиса."""
    return {"status": "ok"}