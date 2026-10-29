"""CV-воркер: отдельный сервис анализа видеопотока и детекции нарушений.

Фаза 3. Содержит интерфейс модуля детекции (:mod:`worker.modules.base`),
заглушку детекции (:mod:`worker.modules.mock`), чтение RTSP-потока
(:mod:`worker.stream`) и публикацию событий в Redis (:mod:`worker.publisher`).
"""
from __future__ import annotations

__version__ = "0.1.0"