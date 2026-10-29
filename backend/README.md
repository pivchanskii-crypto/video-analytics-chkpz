# Video Surveillance Platform — Backend

Бэкенд платформы видеонаблюдения (FastAPI + SQLAlchemy + PostgreSQL + Redis).

## Текущий этап
Фаза 5: бизнес-логика нарушений (дедупликация, проверка времени в зоне) и
Email-оповещения операторов по SMTP.

## Установка
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заполнить DATABASE_URL, JWT_SECRET_KEY и SMTP_*
```

## Миграции (Alembic)
```bash
# сгенерировать начальную ревизию по моделям
alembic revision --autogenerate -m "init db schema"
# применить миграции
alembic upgrade head
```

## Запуск
```bash
uvicorn app.main:app --reload
```

## Эндпоинты
- `POST /api/v1/auth/login`  — `{"login": "...", "password": "..."}`
- `POST /api/v1/auth/refresh` — `{"refresh_token": "..."}`
- `GET /health`

Камеры (заголовок `Authorization: Bearer <access_token>`):
- `GET    /api/v1/cameras` — список камер (оператор видит только назначенные)
- `POST   /api/v1/cameras` — добавить камеру по RTSP (админ)
- `GET    /api/v1/cameras/{id}` — получить камеру
- `PATCH  /api/v1/cameras/{id}` — изменить камеру (админ)
- `DELETE /api/v1/cameras/{id}` — удалить камеру (админ)

Зоны:
- `GET    /api/v1/cameras/{id}/zones` — список зон камеры
- `POST   /api/v1/cameras/{id}/zones` — создать зону-полигон (админ)
- `GET    /api/v1/cameras/{id}/zones/{zone_id}` — получить зону
- `PATCH  /api/v1/cameras/{id}/zones/{zone_id}` — изменить зону/тип (админ)
- `DELETE /api/v1/cameras/{id}/zones/{zone_id}` — удалить зону (админ)

Нарушения:
- `GET  /api/v1/violations` — лента с фильтрами `camera_id`, `zone_id`, `type`,
  `date_from`, `date_to`, `include_admitted`, `limit`, `offset`.
  «Допущенные» нарушения (лицо идентифицировано и имеет разрешение на зону)
  по умолчанию скрыты.
- `POST /api/v1/violations/{id}/feedback` — `{"decision": "confirmed"}` или
  `{"decision": "false_alarm"}` (кнопки «Подтвердить» / «Ложная тревога»).

WebSocket:
- `WS /api/v1/ws/violations?token=<access_token>` (или заголовок
  `Authorization: Bearer ...`) — поток новых нарушений, отфильтрованный по
  назначенным камерам оператора.

## Обработка событий и оповещения (Фаза 5)
Фоновый обработчик `app.services.event_handler` слушает очередь Redis
`violations_queue`, куда CV-воркер публикует события. Для каждого события:
- Дедупликация по ключу (камера, зона, тип, track_id) — пока человек не ушёл из
  зоны/кадра, повторная запись не создаётся.
- Проверка зоны: нарушение создаётся, только если трек непрерывно находится в
  зоне дольше `thresholds.zone_stay_seconds` (`backend/config.yaml`, по умолчанию
  3 секунды). Время «жизни» трека после последнего события задаётся
  `thresholds.presence_ttl_seconds`.

Новое нарушение:
1. сохраняется в БД вместе с `alerts` (статус `pending`);
2. рассылается Email-оповещение по SMTP (`app.services.notification_service`)
   назначенным операторам (связка `operator_camera`, роль `operator`). Кадр
   прикрепляется из `violations.frame_path`. Срок доставки — не более
   `ALERT_DELIVERY_TIMEOUT_SECONDS` (60 секунд); при срыве срока в лог пишется
   ошибка, а алерт помечается статусом `failed`.

Переменные SMTP задаются в `.env`: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`,
`SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_USE_TLS`, `SMTP_USE_SSL`,
`ALERT_DELIVERY_TIMEOUT_SECONDS`.

## Роли
Зависимость `require_roles("admin", "operator")` из `app.api.deps` ограничивает
доступ к эндпоинтам по ролям пользователя.