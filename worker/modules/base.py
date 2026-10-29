"""Базовый интерфейс модуля детекции (:class:`DetectionModule`)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from worker.core.schemas import Detection, ViolationEvent


class DetectionModule(ABC):
    """Абстрактный базовый класс для всех модулей компьютерного зрения.

    Каждый конкретный модуль отвечает за один класс объектов из ТЗ
    (``person``, ``helmet``, ``safety_vest``). Воркер вызывает
    :meth:`detect` на каждом анализируемом кадре, затем
    :meth:`check_violation` для проверки правил (наличие СИЗ и т.п.).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Уникальное имя модуля (совпадает с классом детекции)."""

    @abstractmethod
    def detect(self, frame: Any) -> list[Detection]:
        """Обнаруживает объекты на кадре.

        :param frame: кадр в формате ``numpy.ndarray`` (BGR) либо иной
            источник кадров (заглушки могут игнорировать содержимое).
        :return: список обнаруженных объектов.
        """

    @abstractmethod
    def check_violation(
        self,
        detections: list[Detection],
        config: dict[str, Any],
    ) -> list[ViolationEvent]:
        """Проверяет обнаруженные объекты по правилам и возвращает нарушения.

        :param detections: результаты :meth:`detect` текущего кадра.
        :param config: параметры проверки (пороги, обязательные СИЗ и т.п.).
        :return: список событий нарушений для публикации в очередь.
        """