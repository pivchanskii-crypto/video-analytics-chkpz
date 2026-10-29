"""Оркестрация обработки кадров: источник -> модули детекции -> очередь."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Protocol

from worker.core.config import settings, worker_config
from worker.modules.base import DetectionModule

logger = logging.getLogger(__name__)


def _safe_timestamp(value: str) -> str:
    """Превращает ISO-метку времени в безопасное имя файла."""
    return re.sub(r"[^0-9A-Za-z_-]", "-", value)


class FrameSource(Protocol):
    """Минимальный интерфейс источника кадров (реализован в ``stream``)."""

    def open(self) -> object: ...
    def read(self) -> Any | None: ...
    def close(self) -> None: ...


class Publisher(Protocol):
    """Минимальный интерфейс брокера (реализован в ``publisher``)."""

    def connect(self) -> object: ...
    def publish(self, message: str) -> None: ...
    def close(self) -> None: ...


class AnalysisPipeline:
    """Читает кадры и с заданной частотой прогоняет модули детекции.

    Частота анализа задаётся параметром ``analyze_every_n``: обрабатывается
    каждый N-й кадр (при 30 fps и ``N=30`` это 1 кадр в секунду).
    """

    def __init__(
        self,
        *,
        camera_id: str,
        frame_source: FrameSource,
        modules: list[DetectionModule],
        publisher: Publisher,
        analyze_every_n: int = 30,
        config: dict[str, Any] | None = None,
        frames_dir: str | None = None,
    ) -> None:
        self.camera_id = camera_id
        self.frame_source = frame_source
        self.modules = modules
        self.publisher = publisher
        self.analyze_every_n = analyze_every_n
        self.config = config or worker_config.model_dump()
        self._frames_dir = frames_dir or settings.FRAMES_DIR

    def run(self) -> None:
        """Запускает бесконечный цикл обработки кадров (до ``Ctrl+C``)."""
        self.frame_source.open()
        self.publisher.connect()
        frame_index = 0
        logger.info(
            "Воркер запущен: camera_id=%s, анализ каждого %s-го кадра",
            self.camera_id,
            self.analyze_every_n,
        )
        try:
            while True:
                frame = self.frame_source.read()
                if frame is None:
                    # Не удалось прочитать кадр: сбой потока/пропуск ключевого кадра.
                    continue
                frame_index += 1
                self.process_frame(frame, frame_index)
        except KeyboardInterrupt:
            logger.info("Получен Ctrl+C — останавливаем воркер")
        finally:
            self.frame_source.close()
            self.publisher.close()

    def process_frame(self, frame: Any, frame_index: int) -> list[str]:
        """Обрабатывает один кадр, если подошло время анализа.

        Возвращает список опубликованных JSON-сообщений (пуст, если кадр
        пропущен из-за частоты анализа или нарушений нет). Выделен в отдельный
        метод для удобства тестирования.
        """
        if frame_index % self.analyze_every_n != 0:
            return []
        return self._analyze_frame(frame)

    def _analyze_frame(self, frame: Any) -> list[str]:
        published: list[str] = []
        for module in self.modules:
            try:
                detections = module.detect(frame)
                events = module.check_violation(detections, self.config)
            except Exception:  # noqa: BLE001 — не роняем воркер из-за одного кадра
                logger.exception("Ошибка модуля %s", getattr(module, "name", module))
                continue
            for event in events:
                event.frame_path = self._save_frame(
                    frame,
                    camera_id=self.camera_id,
                    timestamp=event.timestamp,
                )
                message = event.to_json()
                self.publisher.publish(message)
                published.append(message)
                logger.info("Опубликовано нарушение: %s", message)
        return published

    def _save_frame(
        self,
        frame: Any,
        *,
        camera_id: str,
        timestamp: str,
    ) -> str | None:
        """Сохраняет кадр нарушения на диск и возвращает путь к файлу.

        Кадр сохраняется в ``/app/frames/{camera_id}_{timestamp}.jpg``
        (каталог настраивается через ``FRAMES_DIR``). Если кадра нет или
        ``opencv-python`` недоступен, возвращается ``None`` — событие всё равно
        публикуется, но без ссылки на кадр.
        """
        if frame is None:
            return None

        try:
            import cv2
        except ImportError as exc:
            logger.warning("opencv-python не установлен — кадр не сохранён: %s", exc)
            return None

        filename = f"{camera_id}_{_safe_timestamp(timestamp)}.jpg"
        frames_dir = Path(self._frames_dir)
        try:
            frames_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning("Каталог кадров %s недоступен: %s", frames_dir, exc)
            return None

        path = frames_dir / filename
        if cv2.imwrite(str(path), frame):
            return str(path)

        logger.warning("Не удалось сохранить кадр %s", path)
        return None