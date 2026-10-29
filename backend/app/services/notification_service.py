"""Доставка Email-оповещений по SMTP (Фаза 5).

Отправка выполняется в отдельном потоке, а жёсткий срок доставки
(``ALERT_DELIVERY_TIMEOUT_SECONDS``) контролируется через
:func:`send_email_with_deadline`. При превышении срока поднимается
:class:`NotificationError`, а задача считается сорванной.
"""
from __future__ import annotations

import concurrent.futures
import logging
import mimetypes
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import settings

logger = logging.getLogger(__name__)

# Общий пул потоков SMTP-отправки. Потоки не блокируют event loop.
_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="smtp-sender",
)


class NotificationError(Exception):
    """Не удалось доставить оповещение (ошибка отправки или таймаут)."""


def _is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"}


def _load_attachment(frame_path: str | None) -> tuple[str, bytes] | None:
    """Читает кадр для вложения из локального файла или URL, либо ``None``."""
    if not frame_path:
        return None

    try:
        if _is_url(frame_path):
            import urllib.request

            with urllib.request.urlopen(frame_path, timeout=10) as response:
                data = response.read()
        else:
            data = Path(frame_path).read_bytes()
    except Exception as exc:  # noqa: BLE001 — кадр необязателен для доставки
        logger.warning("Не удалось прочитать кадр %s: %s", frame_path, exc)
        return None

    filename = Path(urlparse(frame_path).path).name or "frame.jpg"
    return filename, data


def send_email(
    *,
    to: str,
    subject: str,
    body: str,
    frame_path: str | None = None,
    timeout: float = 60.0,
) -> None:
    """Формирует и отправляет письмо через SMTP.

    При наличии кадра он прикрепляется к письму; ссылка на кадр также
    включается в текст письма (``frame_path`` берётся из записи нарушения в БД).
    """
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.SMTP_FROM
    message["To"] = to
    message.set_content(body)

    attachment = _load_attachment(frame_path)
    if attachment is not None:
        filename, data = attachment
        ctype = mimetypes.guess_type(filename)[0] or "image/jpeg"
        maintype, subtype = ctype.split("/", 1)
        message.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)

    context = (
        ssl.create_default_context()
        if (settings.SMTP_USE_TLS or settings.SMTP_USE_SSL)
        else None
    )

    if settings.SMTP_USE_SSL:
        server: smtplib.SMTP = smtplib.SMTP_SSL(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=timeout,
            context=context,
        )
    else:
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout)

    try:
        if settings.SMTP_USE_TLS and not settings.SMTP_USE_SSL:
            server.starttls(context=context)
        if settings.SMTP_USERNAME:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(message)
    finally:
        try:
            server.quit()
        except Exception:  # noqa: BLE001
            pass
        server.close()


def send_email_with_deadline(
    *,
    to: str,
    subject: str,
    body: str,
    frame_path: str | None = None,
    deadline_seconds: float | None = None,
) -> None:
    """Отправляет письмо с жёстким ограничением времени доставки.

    Время контролируется через ``future.result(timeout=...)``. При превышении
    поднимается :class:`NotificationError`; поток-отправитель не прерывается,
    но доставка считается сорванной (алерт будет помечен как failed).
    """
    deadline = float(
        deadline_seconds
        if deadline_seconds is not None
        else settings.ALERT_DELIVERY_TIMEOUT_SECONDS
    )

    future = _executor.submit(
        send_email,
        to=to,
        subject=subject,
        body=body,
        frame_path=frame_path,
        timeout=deadline,
    )
    try:
        future.result(timeout=deadline)
    except concurrent.futures.TimeoutError as exc:
        raise NotificationError(
            f"Срок доставки истёк ({deadline:g}с)"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise NotificationError(f"Ошибка отправки: {exc}") from exc