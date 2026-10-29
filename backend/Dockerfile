# Backend (FastAPI + SQLAlchemy + Alembic). Базовый образ соответствует
# версии Python в локальном venv (3.13).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# psycopg2-binary — готовый wheel, дополнительные системные библиотеки не нужны.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Исходники приложения, конфигурация и миграции Alembic.
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY config.yaml .
COPY entrypoint.sh .

RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

# Миграции -> сидинг -> запуск FastAPI.
ENTRYPOINT ["sh", "/app/entrypoint.sh"]