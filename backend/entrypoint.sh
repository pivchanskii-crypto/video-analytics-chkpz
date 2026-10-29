#!/bin/sh
set -e

echo "==> Применение миграций БД (Alembic)..."
alembic upgrade head

echo "==> Сидинг начальных данных (камеры/администратор)..."
python -m app.seed

echo "==> Запуск FastAPI (uvicorn) на 0.0.0.0:8000..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000