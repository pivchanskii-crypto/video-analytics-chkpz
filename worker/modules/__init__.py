"""Модули компьютерного зрения.

Здесь располагаются реализации :class:`DetectionModule` для каждого класса
детекции (``person``, ``helmet``, ``safety_vest``). В фазе 3 используется
заглушка :class:`MockModule`; реальные модули на базе Ultralytics появятся в
следующих фазах.
"""
from __future__ import annotations

from worker.modules.base import DetectionModule
from worker.modules.mock import MockModule

__all__ = ["DetectionModule", "MockModule"]