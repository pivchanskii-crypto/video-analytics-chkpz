"""Публикация событий нарушений в Redis (очередь ``violations_queue``)."""
from __future__ import annotations

from worker.core.config import settings


class PublisherError(RuntimeError):
    """Ошибка работы с брокером Redis."""


class RedisPublisher:
    """Публикует JSON-сообщения в очередь Redis.

    Сообщения добавляются в хвост очереди (``RPUSH``); потребители читают с
    головы (``BLPOP``). Клиент ``redis`` импортируется лениво — модуль можно
    импортировать без установленного пакета ``redis``.
    """

    def __init__(self, redis_url: str | None = None, queue: str | None = None) -> None:
        self.redis_url = redis_url or settings.REDIS_URL
        self.queue = queue or settings.VIOLATIONS_QUEUE
        self._client = None

    def connect(self) -> "RedisPublisher":
        """Подключается к Redis и проверяет соединение (``PING``)."""
        try:
            import redis
        except ImportError as exc:
            raise PublisherError("Пакет redis не установлен") from exc

        self._client = redis.Redis.from_url(self.redis_url)
        try:
            self._client.ping()
        except Exception as exc:  # noqa: BLE001 — любая ошибка сокета = нет связи
            raise PublisherError(f"Нет соединения с Redis ({self.redis_url})") from exc
        return self

    def publish(self, message: str) -> None:
        """Публикует готовую JSON-строку в очередь."""
        if self._client is None:
            raise PublisherError("Не подключён к Redis — вызовите connect()")
        self._client.rpush(self.queue, message)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None