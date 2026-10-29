"""Юнит-тесты ядра CV-воркера (stdlib ``unittest``).

Запуск (из корня репозитория):
    python -m unittest worker.tests.test_pipeline -v
"""
from __future__ import annotations

import json
import unittest

from worker.core.enums import DetectionClass, ViolationType
from worker.core.schemas import ViolationEvent
from worker.modules.base import DetectionModule
from worker.modules.mock import MockModule
from worker.pipeline import AnalysisPipeline


class _FakePublisher:
    """Собирает опубликованные сообщения вместо Redis."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def connect(self) -> "_FakePublisher":
        return self

    def publish(self, message: str) -> None:
        self.messages.append(message)

    def close(self) -> None:
        pass


class DetectionModuleTests(unittest.TestCase):
    def test_is_abstract(self) -> None:
        with self.assertRaises(TypeError):
            DetectionModule()  # type: ignore[abstract]


class MockModuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = MockModule(camera_id="cam-1")

    def test_name(self) -> None:
        self.assertEqual(self.module.name, DetectionClass.PERSON.value)

    def test_detect_returns_person_without_helmet(self) -> None:
        detections = self.module.detect(None)
        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0].class_name, DetectionClass.PERSON)
        self.assertFalse(detections[0].attributes["helmet"])

    def test_check_violation_returns_no_pre_event(self) -> None:
        detections = self.module.detect(None)
        events = self.module.check_violation(detections, {})
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, ViolationType.NO_PRE)

    def test_check_violation_rate_limited(self) -> None:
        module = MockModule(camera_id="cam-1", min_interval_seconds=3600)
        detections = module.detect(None)
        self.assertEqual(len(module.check_violation(detections, {})), 1)
        self.assertEqual(module.check_violation(detections, {}), [])


class ViolationEventTests(unittest.TestCase):
    def test_message_structure(self) -> None:
        event = ViolationEvent.create(
            camera_id="cam-1",
            track_id="42",
            violation_type=ViolationType.NO_PRE,
        )
        payload = json.loads(event.to_json())
        self.assertEqual(set(payload), {"camera_id", "track_id", "type", "timestamp"})
        self.assertEqual(payload["camera_id"], "cam-1")
        self.assertEqual(payload["track_id"], "42")
        self.assertEqual(payload["type"], "no_pre")
        self.assertIn("T", payload["timestamp"])


class PipelineTests(unittest.TestCase):
    def test_analyzes_only_every_nth_frame(self) -> None:
        publisher = _FakePublisher()
        pipeline = AnalysisPipeline(
            camera_id="cam-1",
            frame_source=object(),  # не используется в process_frame
            modules=[MockModule(camera_id="cam-1")],
            publisher=publisher,
            analyze_every_n=30,
        )
        # Кадры 1..29 пропускаются (частота анализа: каждый 30-й кадр).
        for idx in range(1, 30):
            self.assertEqual(pipeline.process_frame(None, idx), [])
        # 30-й кадр анализируется и публикует одно событие.
        messages = pipeline.process_frame(None, 30)
        self.assertEqual(len(messages), 1)
        payload = json.loads(messages[0])
        self.assertEqual(payload["camera_id"], "cam-1")
        self.assertEqual(payload["type"], "no_pre")
        self.assertEqual(len(publisher.messages), 1)


if __name__ == "__main__":
    unittest.main()