# CV-воркер (OpenCV + Redis publisher). Базовый образ соответствует версии
# Python в локальном venv (3.13).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Системные библиотеки, которые требуются opencv-python (не headless) при
# импорте cv2 и чтении RTSP-потока.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

# Контекст сборки — каталог worker/, поэтому копируем его содержимое в /app/worker:
# __init__.py, core/, modules/, stream.py, publisher.py, pipeline.py, main.py и
# config.yaml (worker/core/config.py ищет config.yaml именно в каталоге пакета).
COPY . ./worker

CMD ["python", "-m", "worker.main"]