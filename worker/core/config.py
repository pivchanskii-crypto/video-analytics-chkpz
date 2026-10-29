"""Конфигурация CV-воркера.

Секреты и инфраструктурные настройки читаются из ``.env`` (``Settings``).
Прикладные настройки (частота анализа, классы детекции) — из ``config.yaml``
(``WorkerConfig``).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

# Корень воркера: .../worker/ (родитель каталога core).
BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Параметры окружения, загружаемые из ``.env``."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # --- Redis (брокер очередей) ---
    REDIS_URL: str = "redis://localhost:6379/0"
    VIOLATIONS_QUEUE: str = "violations_queue"

    # --- RTSP-поток ---
    RTSP_URL: str = ""
    CAMERA_ID: str = "0"

    # --- Каталог для сохранения кадров нарушений ---
    FRAMES_DIR: str = "/app/frames"


@lru_cache
def get_settings() -> Settings:
    """Возвращает закэшированный синглтон настроек окружения."""
    return Settings()


class WorkerConfig(BaseModel):
    """Прикладная конфигурация из ``config.yaml``."""

    worker: dict[str, Any] = {"analyze_every_n": 30, "fps": 30}
    detection_classes: list[str] = ["person", "helmet", "safety_vest"]


@lru_cache
def get_worker_config() -> WorkerConfig:
    """Загружает и кэширует ``config.yaml``."""
    config_path = BASE_DIR / "config.yaml"
    raw: dict[str, Any] = {}
    if config_path.exists():
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return WorkerConfig(**raw)


settings = get_settings()
worker_config = get_worker_config()