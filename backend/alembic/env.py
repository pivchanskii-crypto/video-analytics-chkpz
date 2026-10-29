"""Конфигурация Alembic.

URL подключения читается из настроек (``.env``), metadata — из базового
класса всех ORM-моделей. Перед генерацией/применением миграций все модели
должны быть импортированы (см. ``from app import models``).
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.orm import configure_mappers

from app import models  # noqa: F401  # регистрирует все модели в Base.metadata
from app.core.config import settings
from app.core.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Переопределяем URL из alembic.ini значением из .env.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Разрешаем все строковые forward-ссылки в relationship до чтения metadata.
configure_mappers()
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Генерирует SQL миграций без подключения к БД."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Применяет миграции с реальным подключением к БД."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()