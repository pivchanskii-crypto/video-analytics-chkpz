"""Источники кадров: чтение RTSP-потока через OpenCV и тестовый генератор."""
from __future__ import annotations

import time
from typing import Any


class FrameSourceError(RuntimeError):
    """Ошибка открытия/чтения источника кадров."""


class RTSPFrameSource:
    """Читает кадры из RTSP-потока через ``cv2.VideoCapture``.

    ``opencv-python`` импортируется лениво (внутри :meth:`open`), чтобы модуль
    был импортируем без установленного пакета (например, в юнит-тестах).
    """

    def __init__(self, rtsp_url: str) -> None:
        self.rtsp_url = rtsp_url
        self._capture = None

    def open(self) -> "RTSPFrameSource":
        """Открывает RTSP-поток и возвращает себя для цепочки вызовов."""
        if not self.rtsp_url:
            raise FrameSourceError("RTSP_URL не задан")
        try:
            import cv2
        except ImportError as exc:
            raise FrameSourceError("Пакет opencv-python не установлен") from exc

        self._capture = cv2.VideoCapture(self.rtsp_url)
        if not self._capture.isOpened():
            self._capture.release()
            self._capture = None
            raise FrameSourceError(f"Не удалось открыть RTSP-поток: {self.rtsp_url}")
        return self

    def read(self) -> Any | None:
        """Возвращает очередной кадр (``numpy.ndarray``, BGR) или ``None``."""
        if self._capture is None:
            raise FrameSourceError("Источник не открыт — вызовите open()")
        ok, frame = self._capture.read()
        return frame if ok else None

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    def __enter__(self) -> "RTSPFrameSource":
        return self.open()

    def __exit__(self, *exc_info: object) -> None:
        self.close()


class SyntheticFrameSource:
    """Генерирует тестовые кадры («чёрный экран») без реальной камеры.

    Используется как fallback, когда ``RTSP_URL`` не задан или поток недоступен,
    чтобы воркер можно было запустить в Docker без реальной камеры и проверить
    сквозной путь «воркер → Redis → бэкенд → БД». ``numpy`` импортируется
    лениво (внутри :meth:`open`), чтобы модуль оставался импортируемым без
    установленного пакета.
    """

    def __init__(self, width: int = 640, height: int = 480, fps: int = 30) -> None:
        self.width = width
        self.height = height
        self.fps = fps
        self._np = None
        self._frame_interval = 1.0 / max(1, fps)

    def open(self) -> "SyntheticFrameSource":
        try:
            import numpy as np
        except ImportError as exc:
            raise FrameSourceError("Пакет numpy не установлен") from exc
        self._np = np
        return self

    def read(self) -> Any | None:
        """Возвращает чёрный кадр (``numpy.ndarray``, BGR) раз в ``1/fps`` сек.

        Содержимое кадра значения не имеет: модули-заглушки его игнорируют, а
        небольшая задержка имитирует частоту кадров, чтобы цикл анализа шёл с
        реалистичным темпом, а не «крутился» вхолостую на полной скорости.
        """
        if self._np is None:
            raise FrameSourceError("Источник не открыт — вызовите open()")
        frame = self._np.zeros((self.height, self.width, 3), dtype=self._np.uint8)
        time.sleep(self._frame_interval)
        return frame

    def close(self) -> None:
        self._np = None

    def __enter__(self) -> "SyntheticFrameSource":
        return self.open()

    def __exit__(self, *exc_info: object) -> None:
        self.close()