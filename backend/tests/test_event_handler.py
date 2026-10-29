"""Юнит-тесты обработчика событий нарушений (Фаза 5).

Запуск (из каталога ``backend``):
    python -m unittest tests.test_event_handler -v
"""
from __future__ import annotations

import unittest

from app.core.enums import ViolationType
from app.services.event_handler import DedupGate, parse_event_message


class ParseEventMessageTests(unittest.TestCase):
    def test_valid_message_with_zone_and_frame(self) -> None:
        raw = (
            '{"camera_id": "1", "zone_id": "7", "track_id": "42", '
            '"type": "no_pre", "timestamp": "2026-10-27T20:00:00+00:00", '
            '"frame_path": "http://storage/frames/42.jpg"}'
        )
        event = parse_event_message(raw)
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event["camera_id"], 1)
        self.assertEqual(event["zone_id"], 7)
        self.assertEqual(event["track_id"], "42")
        self.assertEqual(event["type"], ViolationType.NO_PRE)
        self.assertEqual(event["frame_path"], "http://storage/frames/42.jpg")

    def test_invalid_json(self) -> None:
        self.assertIsNone(parse_event_message("not-json"))

    def test_unknown_type(self) -> None:
        self.assertIsNone(
            parse_event_message('{"camera_id": 1, "track_id": "1", "type": "no_helmet"}')
        )

    def test_non_integer_camera_id(self) -> None:
        self.assertIsNone(
            parse_event_message('{"camera_id": "cam-1", "track_id": "1", "type": "no_pre"}')
        )


class DedupGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = DedupGate(stay_seconds=3.0, ttl_seconds=30.0)
        self.key = (1, 7, "no_pre", "42")

    def test_does_not_create_before_stay(self) -> None:
        self.assertFalse(self.gate.observe(self.key, 0.0))
        self.assertFalse(self.gate.observe(self.key, 2.9))

    def test_creates_once_after_stay_and_deduplicates(self) -> None:
        self.assertFalse(self.gate.observe(self.key, 0.0))
        self.assertTrue(self.gate.observe(self.key, 3.0))
        self.gate.mark_emitted(self.key)
        # Пока трек жив в зоне/кадре — повторная запись не создаётся.
        self.assertFalse(self.gate.observe(self.key, 4.0))
        self.assertFalse(self.gate.observe(self.key, 10.0))

    def test_ttl_purge_allows_new_violation_after_leave(self) -> None:
        self.assertFalse(self.gate.observe(self.key, 0.0))
        self.assertTrue(self.gate.observe(self.key, 3.0))
        self.gate.mark_emitted(self.key)
        self.assertFalse(self.gate.observe(self.key, 4.0))
        # После TTL без событий человек считается ушедшим: ключ очищается.
        self.assertFalse(self.gate.observe(self.key, 35.0))
        self.assertTrue(self.gate.observe(self.key, 38.0))

    def test_reset_allows_retry(self) -> None:
        self.assertFalse(self.gate.observe(self.key, 0.0))
        self.gate.reset(self.key)
        self.assertFalse(self.gate.observe(self.key, 1.0))


if __name__ == "__main__":
    unittest.main()