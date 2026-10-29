"""Конфигурация приложения.

Секреты и инфраструктурные настройки читаются из переменных окружения
(``.env``) через ``Settings``. Прикладные настройки предметной области
(пороги, классы СИЗ, камеры) хранятся в ``config.yaml`` через ``AppConfig``.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

# Корень проекта: .../backend/ (родитель каталога app/core).
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Параметры окружения, загружаемые из ``.env``."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # --- База данных ---
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/surveillance"

    # --- JWT / безопасность ---
    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    # Сроки жизни токенов из ТЗ: access — 1 час, refresh — 7 дней.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- Redis (трансляция нарушений по WebSocket) ---
    REDIS_URL: str = "redis://localhost:6379/0"
    VIOLATIONS_QUEUE: str = "violations_queue"

    # --- SMTP (Email-оповещения, Фаза 5) ---
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 25
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@example.com"
    # STARTTLS (порт 587) либо прямой SSL (порт 465).
    SMTP_USE_TLS: bool = False
    SMTP_USE_SSL: bool = False
    # Максимальное время доставки оповещения (сек). При превышении — алерт сорван.
    ALERT_DELIVERY_TIMEOUT_SECONDS: int = 60

    # --- Приложение ---
    DEBUG: bool = False

    # --- Кадры нарушений (статическая раздача) ---
    FRAMES_DIR: str = "/app/frames"


@lru_cache
def get_settings() -> Settings:
    """Возвращает закэшированный синглтон настроек окружения."""
    return Settings()


class AppConfig(BaseModel):
    """Прикладная конфигурация из ``config.yaml``.

    Здесь живут не секретные настройки предметной области. Секреты и
    инфраструктура — в ``.env`` (класс :class:`Settings`).
    """

    app: dict[str, Any] = {}
    cors: dict[str, list[str]] = {
        "allowed_origins": ["http://localhost:3000", "http://localhost:8080"]
    }
    thresholds: dict[str, Any] = {}
    ppe_classes: list[str] = []
    cameras: list[dict[str, Any]] = []


@lru_cache
def get_app_config() -> AppConfig:
    """Загружает и кэширует ``config.yaml``."""
    config_path = BASE_DIR / "config.yaml"
    raw: dict[str, Any] = {}
    if config_path.exists():
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return AppConfig(**raw)


settings = get_settings()
app_config = get_app_config()