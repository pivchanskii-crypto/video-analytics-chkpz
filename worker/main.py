"""Точка входа CV-воркера.

Пример запуска (из корня репозитория):
    python -m worker.main --rtsp-url rtsp://user:pass@host:554/stream --camera-id 1

Если ``RTSP_URL`` не задан или поток недоступен, воркер автоматически
переключается на синтетический источник кадров («чёрный экран»), чтобы можно
было проверить сквозной путь «воркер → Redis → бэкенд → БД» без реальной камеры.
"""
from __future__ import annotations

import argparse
import logging

from worker.core.config import settings, worker_config
from worker.modules.mock import MockModule
from worker.pipeline import AnalysisPipeline
from worker.publisher import RedisPublisher
from worker.stream import FrameSourceError, RTSPFrameSource, SyntheticFrameSource

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CV-воркер: анализ RTSP-потока и публикация нарушений в Redis",
    )
    parser.add_argument("--rtsp-url", default=settings.RTSP_URL, help="URL RTSP-потока")
    parser.add_argument(
        "--camera-id",
        default=settings.CAMERA_ID,
        help="Идентификатор камеры (попадает в сообщение о нарушении)",
    )
    parser.add_argument(
        "--analyze-every-n",
        type=int,
        default=worker_config.worker.get("analyze_every_n", 30),
        help="Анализировать каждый N-й кадр (по умолчанию 30 => 1 кадр/с при 30 fps)",
    )
    return parser


def build_frame_source(rtsp_url: str) -> RTSPFrameSource | SyntheticFrameSource:
    """Возвращает источник кадров: RTSP-поток либо тестовый «чёрный экран».

    Сначала пробуем открыть RTSP-поток. При пустом URL или ошибке открытия не
    падаем, а продолжаем работу на синтетических кадрах — это позволяет поднять
    воркер в Docker без реальной камеры. Успешно открытый пробник закрываем,
    чтобы :meth:`AnalysisPipeline.run` открыл источник заново штатным образом.
    """
    if not rtsp_url:
        logger.warning("RTSP_URL не задан — использую тестовый источник (чёрный экран)")
        return SyntheticFrameSource()

    source = RTSPFrameSource(rtsp_url)
    try:
        source.open()
    except FrameSourceError as exc:
        logger.warning(
            "Не удалось открыть RTSP-поток (%s) — использую тестовый источник (чёрный экран)",
            exc,
        )
        return SyntheticFrameSource()

    source.close()
    return source


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = build_parser().parse_args()

    modules = [MockModule(camera_id=args.camera_id)]
    frame_source = build_frame_source(args.rtsp_url)
    publisher = RedisPublisher()

    pipeline = AnalysisPipeline(
        camera_id=args.camera_id,
        frame_source=frame_source,
        modules=modules,
        publisher=publisher,
        analyze_every_n=args.analyze_every_n,
    )
    pipeline.run()


if __name__ == "__main__":
    main()