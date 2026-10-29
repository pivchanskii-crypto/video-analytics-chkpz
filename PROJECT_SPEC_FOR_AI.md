# PROJECT_SPEC_FOR_AI

Снимок бэкенда Video Surveillance Platform по публичному репозиторию [weeqle/deepseek_dev](https://github.com/weeqle/deepseek_dev), ветка `main`, коммит `bf59736` (29 октября 2026, 08:51 YEKT, сообщение «Add files via upload»).

Это описание того, что реально лежит в коде на фазе 5. Требования ТЗ, которых в коде нет, вынесены в раздел 8 и не смешаны с контрактом.

Стек: FastAPI, SQLAlchemy 2 (синхронный движок), Alembic, PostgreSQL (JSONB), Redis (список `violations_queue`), SMTP. CV-воркер в репозитории — заготовка: конфигурация, enum и скомпилированная схема события. Чтение RTSP, детекция и публикация в очередь не реализованы.

---

## 1. Структура проекта

```text
deepseek_dev/
├── backend/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── README.md
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── config.yaml
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       ├── 03221246778b_init_db_schema.py
│   │       └── 1a2b3c4d5e6f_add_user_email.py
│   ├── app/
│   │   ├── main.py
│   │   ├── seed.py
│   │   ├── api/
│   │   │   ├── deps.py
│   │   │   └── v1/
│   │   │       ├── auth.py
│   │   │       ├── cameras.py
│   │   │       ├── zones.py
│   │   │       ├── violations.py
│   │   │       └── ws.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── enums.py
│   │   │   ├── security.py
│   │   │   └── types.py
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── camera.py
│   │   │   ├── zone.py
│   │   │   ├── zone_permission.py
│   │   │   ├── operator_camera.py
│   │   │   ├── face.py
│   │   │   ├── violation.py
│   │   │   ├── alert.py
│   │   │   └── audit_log.py
│   │   ├── schemas/
│   │   │   ├── auth.py
│   │   │   ├── camera.py
│   │   │   └── violation.py
│   │   └── services/
│   │       ├── auth_service.py
│   │       ├── access_service.py
│   │       ├── violation_service.py
│   │       ├── event_handler.py
│   │       ├── notification_service.py
│   │       └── ws_manager.py
│   └── tests/
│       └── test_event_handler.py
└── worker/
    └── core/
        ├── __init__.py
        ├── config.py
        ├── enums.py
        └── __pycache__/schemas.cpython-313.pyc   # исходника schemas.py нет
```

В git также закоммичены каталоги `__pycache__` (CPython 3.13). Файла `.env.example` нет, хотя README просит `cp .env.example .env`. Фронтенда, `docker-compose`, таблицы `workers` и исходника `worker/core/schemas.py` нет.

| Модуль | Назначение |
| --- | --- |
| `app/main.py` | FastAPI, CORS, роутеры `/api/v1`, lifespan с потребителем очереди |
| `app/core/config.py` | `Settings` из `.env`, `AppConfig` из `config.yaml` |
| `app/core/database.py` | sync engine, `SessionLocal`, `get_db` |
| `app/core/enums.py` | роли, типы зон и нарушений, статусы. Хранятся как строки `.value` |
| `app/core/security.py` | bcrypt и JWT (PyJWT, HS256) |
| `app/core/types.py` | `sa_enum`: VARCHAR, `native_enum=False`, в колонку пишется `.value`, не имя члена |
| `app/api/deps.py` | Bearer access-токен, `require_roles`, доступ к камере |
| `app/api/v1/*` | HTTP и WebSocket |
| `app/services/event_handler.py` | Фаза 5: очередь, дедуп, порог пребывания, запись, почта, WS |
| `app/services/notification_service.py` | SMTP и вложение кадра |
| `app/services/ws_manager.py` | Реестр сокетов и `broadcast` по `camera_id` |
| `app/services/violation_service.py` | Фильтры ленты и флаг `admitted` |
| `app/services/access_service.py` | Админ видит все камеры, оператор — строки `operator_camera` |
| `app/seed.py` | Идемпотентный сид камер и админа при старте контейнера |
| `worker/core` | Настройки воркера и enum классов детекции. Цикла анализа нет |

---

## 2. Технологический стек и зависимости

Образ: `python:3.13-slim` (`backend/Dockerfile`). Байткод в репозитории собран CPython 3.13.

`backend/requirements.txt` задаёт нижние границы, не точные пины:

```text
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
SQLAlchemy>=2.0.30
alembic>=1.13.0
psycopg2-binary>=2.9.9
pydantic>=2.7.0
pydantic-settings>=2.3.0
PyJWT>=2.8.0
bcrypt>=4.1.0
PyYAML>=6.0.1
redis>=5.0.0
```

Redis импортируется лениво (`redis.asyncio`). Если пакета нет или `ping` падает, HTTP-API всё равно поднимается, обработка очереди отключается.

### 2.1. SQLAlchemy

Синхронный движок, не async:

```python
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(
    bind=engine, autocommit=False, autoflush=False, expire_on_commit=False,
)
```

URL по умолчанию: `postgresql+psycopg2://postgres:postgres@localhost:5432/surveillance`.

`get_db` открывает сессию на запрос и закрывает её в `finally`. Именование ограничений зафиксировано (`ix_%(column_0_label)s`, `fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s` и т.д.), чтобы Alembic не переименовывал их при autogenerate.

Alembic берёт URL из `settings.DATABASE_URL`, metadata — из `Base`. Ревизии: `03221246778b` (вся схема), затем `1a2b3c4d5e6f` (колонка `users.email`).

JSONB используется для `cameras.config`, `zones.polygon`, `faces.embedding`. Enum-колонки — VARCHAR(20), не native PostgreSQL ENUM.

### 2.2. Redis

Один URL и одно имя списка:

- `REDIS_URL`, по умолчанию `redis://localhost:6379/0`
- `VIOLATIONS_QUEUE`, по умолчанию `violations_queue`

Клиент: `redis.asyncio.Redis.from_url(..., decode_responses=True)`. Чтение: `BLPOP key timeout=1`. Сообщение — JSON-строка. Отдельной Redis Streams, pub/sub и второй БД Redis нет.

Потребитель стартует в `lifespan` (`run_event_consumer`). Функция `stream_redis_violations` в `ws_manager.py` тоже делает `BLPOP` той же очереди, но из `main.py` не вызывается. Если запустить оба цикла, они будут забирать сообщения друг у друга: сырое сообщение уйдёт в сокет в обход дедупа и записи в БД.

### 2.3. Переменные окружения

`.env.example` в репозитории нет. Имена берутся из `Settings` (`pydantic-settings`, файл `backend/.env`, `case_sensitive=True`, `extra="ignore"`) и из `os.getenv` в сиде. У воркера свой `Settings` и файл `worker/.env`.

Бэкенд:

| Переменная | Значение по умолчанию |
| --- | --- |
| `DATABASE_URL` | `postgresql+psycopg2://postgres:postgres@localhost:5432/surveillance` |
| `JWT_SECRET_KEY` | `change-me` |
| `JWT_ALGORITHM` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` |
| `REDIS_URL` | `redis://localhost:6379/0` |
| `VIOLATIONS_QUEUE` | `violations_queue` |
| `SMTP_HOST` | `localhost` |
| `SMTP_PORT` | `25` |
| `SMTP_USERNAME` | пусто (логин не выполняется) |
| `SMTP_PASSWORD` | пусто |
| `SMTP_FROM` | `noreply@example.com` |
| `SMTP_USE_TLS` | `false` (STARTTLS) |
| `SMTP_USE_SSL` | `false` (SMTP_SSL, обычно порт 465) |
| `ALERT_DELIVERY_TIMEOUT_SECONDS` | `60` |
| `DEBUG` | `false` |
| `SEED_CAMERA_IDS` | пусто. Список id через запятую |
| `SEED_ADMIN_LOGIN` | пусто. Если пусто, админ не создаётся |
| `SEED_ADMIN_PASSWORD` | `admin` |
| `SEED_ADMIN_EMAIL` | пусто → `NULL` |

Воркер (отдельный процесс, своего цикла нет):

| Переменная | Значение по умолчанию |
| --- | --- |
| `REDIS_URL` | `redis://localhost:6379/0` |
| `VIOLATIONS_QUEUE` | `violations_queue` |
| `RTSP_URL` | пусто |
| `CAMERA_ID` | `"0"` (строка) |

Пороги фазы 5 лежат не в окружении, а в `backend/config.yaml`:

```yaml
thresholds:
  zone_stay_seconds: 3
  presence_ttl_seconds: 30
ppe_classes: []
cameras: []
cors:
  allowed_origins:
    - "http://localhost:3000"
    - "http://localhost:8080"
```

`config.yaml` кэшируется на процесс (`lru_cache`). Смена файла без перезапуска не подхватывается. `ppe_classes` и `cameras` в yaml бэкенд нигде не читает, кроме загрузки в `AppConfig`.

Контейнер: `alembic upgrade head` → `python -m app.seed` → `uvicorn app.main:app --host 0.0.0.0 --port 8000`.

---

## 3. Схема базы данных

Все PK — `Integer` autoincrement, кроме составных ключей `operator_camera` и `zone_permissions`. Время — `DateTime(timezone=True)`.

### 3.1. `User` → `users`

| Поле | Тип | Ограничения |
| --- | --- | --- |
| `id` | int PK | |
| `login` | `String(255)` | unique, index, NOT NULL |
| `email` | `String(255)` \| NULL | unique, index. Миграция `1a2b3c4d5e6f` |
| `password_hash` | `String(255)` | NOT NULL, bcrypt |
| `role` | VARCHAR, `UserRole` | `admin` \| `operator` |
| `created_at` | timestamptz | server default `now()` |

Связи: `operator_cameras` → `OperatorCamera`, `audit_logs` → `AuditLog`.

Если `email` пуст, получателем письма становится `login`.

### 3.2. `Camera` → `cameras`

| Поле | Тип | Ограничения |
| --- | --- | --- |
| `id` | int PK | |
| `name` | `String(255)` | NOT NULL |
| `rtsp_url` | `String(512)` | unique, NOT NULL |
| `status` | `String(50)` | NOT NULL, default `offline`. Свободная строка, не enum |
| `worker_id` | int \| NULL | без FK. Таблицы `workers` нет |
| `config` | JSONB | NOT NULL, default `{}`. Схема флагов не задана |

Связи: `zones`, `operators` (`OperatorCamera`), `violations`.

`ondelete` со стороны детей: удаление камеры каскадом удаляет зоны, назначения и нарушения.

### 3.3. `Zone` → `zones`

| Поле | Тип | Ограничения |
| --- | --- | --- |
| `id` | int PK | |
| `camera_id` | int FK `cameras.id` | ON DELETE CASCADE, index |
| `name` | `String(255)` | NOT NULL |
| `polygon` | JSONB | NOT NULL, default `[]` |
| `check_type` | VARCHAR, `CheckType` | default `zone_only` |
| `active` | bool | default `true` |

`CheckType`: `pre_in_zone`, `zone_only`, `disabled`.

Строка в коде именно `pre_in_zone`, не `ppe_in_zone`. Так она лежит в миграции и в API. Менять написание без миграции данных и контракта очереди нельзя.

Полигон — JSON-массив точек `[[x, y], ...]`. На API каждая точка — пара чисел в диапазоне `[0, 1]`, точек минимум 3, верхней границы нет. В БД это JSONB без check-constraint: ограничение только в Pydantic.

Связи: `camera`, `face_permissions` (cascade delete-orphan), `violations`.

Обработчик событий `check_type` и `active` не смотрит. Зона нужна ему только чтобы убедиться, что `zone_id` принадлежит `camera_id`.

### 3.4. `ZonePermission` → `zone_permissions`

Составной PK: `zone_id` FK `zones.id` ON DELETE CASCADE, `face_id` FK `faces.id` ON DELETE CASCADE.

Смысл в коде ленты: лицо `identified` с такой парой считается «допущенным» и по умолчанию скрыто. API создания допуска нет.

### 3.5. `OperatorCamera` → `operator_camera`

Составной PK: `operator_id` FK `users.id` ON DELETE CASCADE, `camera_id` FK `cameras.id` ON DELETE CASCADE.

Единственный источник фильтра оператора. Эндпоинта назначения нет: строки можно вставить только напрямую в БД.

### 3.6. `Face` → `faces`

| Поле | Тип | Ограничения |
| --- | --- | --- |
| `id` | int PK | |
| `full_name` | `String(255)` | NOT NULL |
| `position` | `String(255)` \| NULL | |
| `personnel_uid` | `String(255)` \| NULL | unique index |
| `embedding` | JSONB \| NULL | JSON-массив. Комментарий в модели: позже можно сменить на pgvector |
| `photo_path` | `String(512)` \| NULL | путь к файлу, не байты |
| `created_at` | timestamptz | `now()` |

API лиц нет. `event_handler` поля `face_id` не заполняет.

### 3.7. `Violation` → `violations`

| Поле | Тип | Ограничения |
| --- | --- | --- |
| `id` | int PK | |
| `camera_id` | int FK `cameras.id` | ON DELETE CASCADE, index |
| `zone_id` | int \| NULL FK `zones.id` | ON DELETE SET NULL, index |
| `track_id` | `String(255)` \| NULL | index |
| `type` | VARCHAR, `ViolationType` | NOT NULL |
| `timestamp` | timestamptz | NOT NULL, index. Время события от воркера, не `created_at` |
| `frame_path` | `String(512)` \| NULL | путь или URL кадра |
| `face_id` | int \| NULL FK `faces.id` | ON DELETE SET NULL, index |
| `identity_status` | VARCHAR, `IdentityStatus` | default `not_applicable` |
| `status` | VARCHAR, `ViolationStatus` | default `open` |

`ViolationType`: `no_pre`, `zone_entry`, `unauthorized`.

В коде и в тесте тип отсутствия СИЗ — `no_pre`, не `no_ppe`. Очередь с `no_ppe` будет отвергнута как неизвестный тип.

`IdentityStatus`: `identified`, `unknown`, `uncertain`, `not_applicable`.

`ViolationStatus`: `open`, `confirmed`, `false_alarm`.

Отдельной колонки `feedback` нет. Кнопка оператора перезаписывает `status`. Кадр ложной тревоги никуда не копируется.

Связи: `camera`, `zone`, `face`, `alerts` (cascade delete-orphan).

### 3.8. `Alert` → `alerts`

| Поле | Тип | Ограничения |
| --- | --- | --- |
| `id` | int PK | |
| `violation_id` | int FK `violations.id` | ON DELETE CASCADE, index |
| `channel` | `String(50)` | сейчас всегда `"email"` |
| `recipient` | `String(255)` | email или login оператора |
| `sent_at` | timestamptz \| NULL | |
| `status` | `String(50)` | default `pending`. В коде ещё `sent` и `failed`. Не enum |

Один алерт — одна попытка одному получателю. Повторной отправки нет.

### 3.9. `AuditLog` → `audit_log`

`id`, `user_id` FK `users.id` ON DELETE SET NULL, `action` `String(255)`, `entity` `String(255)`, `entity_id` `String(255)` \| NULL, `created_at`.

Модель и таблица есть. Ни один сервис в них не пишет.

### 3.10. Координаты и кадры

- Полигон зоны: JSONB, доли кадра `[0, 1]`, минимум 3 точки. Пример: `[[0.1, 0.2], [0.4, 0.2], [0.4, 0.8]]`.
- Кадр нарушения: строка `frame_path` до 512 символов. Это путь на диске процесса API либо `http`/`https` URL. Байты в БД не хранятся. Отдельного файлового API нет.
- Эталон лица: `photo_path` плюс `embedding` (JSONB). Код загрузки не написан.
- Сид камер пишет `rtsp_url` вида `synthetic://camera-{id}` в обход валидатора API (API принимает только `rtsp://` и `rtsps://`).

---

## 4. API-контракты

Префикс `/api/v1`. Swagger FastAPI поднимается сам (`/docs`). Защищённые методы: `Authorization: Bearer <access_token>`.

Роли: `admin`, `operator`. Админ видит все камеры. Оператор — только id из `operator_camera`. Чужая камера — `403` `{"detail": "Доступ к камере запрещён"}`. Нет камеры — `404`. Нет токена или он не access — `401`.

Лимитов 5 логинов в минуту и 100 запросов на токен в коде нет. Заголовков `X-Frame-Options` и `nosniff` нет. CORS: origins из `config.yaml`, `allow_credentials=true`, methods и headers `*`.

Ошибки валидации — стандартный FastAPI `422`.

### 4.1. Auth

Роль не требуется.

`POST /api/v1/auth/login`

```json
{ "login": "admin", "password": "admin" }
```

`POST /api/v1/auth/refresh`

```json
{ "refresh_token": "<jwt>" }
```

Ответ обоих (`200`):

```json
{
  "access_token": "<jwt>",
  "refresh_token": "<jwt>",
  "token_type": "bearer",
  "access_expires_in": 3600,
  "refresh_expires_in": 604800
}
```

Неверная пара, битый refresh или тип токена не `refresh` — `401`, `detail` текстом `AuthError`.

JWT payload: `sub` (id пользователя строкой), `role`, `type` (`access` \| `refresh`), `iat`, `exp`. Алгоритм из `JWT_ALGORITHM`. Чёрного списка отозванных токенов нет: refresh каждый раз выпускает новую пару, старый refresh остаётся валидным до `exp`.

### 4.2. Cameras

`GET /api/v1/cameras` — admin и operator. Ответ: массив `CameraRead`.

`POST /api/v1/cameras` — только admin, `201`.

```json
{
  "name": "Пресс 1",
  "rtsp_url": "rtsp://10.0.0.5/stream",
  "status": "offline",
  "worker_id": null,
  "config": { "ppe_always": true }
}
```

`status`, `worker_id`, `config` необязательны. `rtsp_url` обязан начинаться с `rtsp://` или `rtsps://`. Повтор URL — `409`.

`GET /api/v1/cameras/{camera_id}` — admin и назначенный operator.

`PATCH /api/v1/cameras/{camera_id}` — только admin. Тело — те же поля, все опциональны. `null` игнорируется, кроме `worker_id`: `null` снимает воркера. Смена `rtsp_url` на занятый — `409`.

`DELETE /api/v1/cameras/{camera_id}` — только admin, `204` без тела. Каскад: зоны, назначения, нарушения.

Ответ камеры:

```json
{
  "id": 1,
  "name": "Пресс 1",
  "rtsp_url": "rtsp://10.0.0.5/stream",
  "status": "offline",
  "worker_id": null,
  "config": {}
}
```

Отдельных `GET /cameras/{id}/status` и `PATCH /cameras/{id}/config` нет. Флаги проверок — произвольный JSON в `config`, воркер их из API не читает.

### 4.3. Zones

Базовый путь: `/api/v1/cameras/{camera_id}/zones`. Доступ к камере проверяется так же.

`GET` — список зон этой камеры, admin и назначенный operator.

`POST` — только admin, `201`.

```json
{
  "name": "У пресса",
  "polygon": [[0.10, 0.20], [0.45, 0.20], [0.40, 0.85]],
  "check_type": "zone_only",
  "active": true
}
```

`check_type`: `pre_in_zone` | `zone_only` | `disabled`. По умолчанию `zone_only`.

`GET /{zone_id}` — одна зона. Чужая камера или нет записи — `404` «Зона не найдена».

`PATCH /{zone_id}` — только admin. Любое подмножество полей. `null` не затирает значение.

`DELETE /{zone_id}` — только admin, `204`.

Ответ:

```json
{
  "id": 7,
  "camera_id": 1,
  "name": "У пресса",
  "polygon": [[0.1, 0.2], [0.45, 0.2], [0.4, 0.85]],
  "check_type": "zone_only",
  "active": true
}
```

Список допущенных лиц в теле зоны не принимается.

### 4.4. Violations

`GET /api/v1/violations` — admin и operator (у оператора неявный фильтр по своим камерам).

Query:

| Параметр | Смысл |
| --- | --- |
| `camera_id` | int. Чужая камера — 403, нет камеры — 404 |
| `zone_id` | int. Нет зоны — 404. Если задан и `camera_id`, зона должна быть этой камеры, иначе 404 |
| `type` | `no_pre` \| `zone_entry` \| `unauthorized` |
| `date_from`, `date_to` | datetime, фильтр по `violations.timestamp`, границы включительно |
| `include_admitted` | bool, default `false`. `true` показывает «допущенных» |
| `limit` | 1…200, default 50 |
| `offset` | ≥ 0, default 0 |

«Допущенный» — `identity_status == identified` и есть строка `zone_permissions` на пару `(zone_id, face_id)`. Это вычисляется, в колонке не хранится. События фазы 5 приходят с `not_applicable` и без `face_id`, поэтому фильтр их не прячет.

Ответ:

```json
{
  "items": [
    {
      "id": 10,
      "camera_id": 1,
      "zone_id": 7,
      "track_id": "42",
      "type": "no_pre",
      "timestamp": "2026-10-27T20:00:03+00:00",
      "frame_path": "/data/frames/42.jpg",
      "face_id": null,
      "identity_status": "not_applicable",
      "status": "open",
      "admitted": false,
      "camera_name": "Пресс 1",
      "zone_name": "У пресса"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

Сортировка: `timestamp DESC`.

`POST /api/v1/violations/{id}/feedback` — admin и оператор своей камеры.

```json
{ "decision": "confirmed" }
```

`decision`: `confirmed` или `false_alarm`. Нет записи — `404`. Чужая камера — `403`. Статус уже не `open` — `409` «Нарушение уже обработано». Успех — тот же объект `ViolationRead`.

### 4.5. Прочее

`GET /health` без префикса и без токена: `{"status": "ok"}`.

Нет эндпоинтов пользователей, лиц, воркеров, отчётов, назначения оператора на камеру.

---

## 5. Ядро бизнес-логики (фаза 5)

Файл `backend/app/services/event_handler.py`. Запускается из `lifespan` как `asyncio.create_task(run_event_consumer)`. На остановке приложения задача отменяется.

### 5.1. Очередь

`BLPOP violations_queue` с таймаутом 1 с. Таймаут без сообщения — продолжить цикл. Ошибка сокета — лог и `sleep(1)`. Тело сообщения обрабатывается в `asyncio.to_thread`, чтобы синхронные БД и SMTP не блокировали event loop.

Ожидаемый JSON (разбирает `parse_event_message`):

```json
{
  "camera_id": 1,
  "zone_id": 7,
  "track_id": "42",
  "type": "no_pre",
  "timestamp": "2026-10-27T20:00:00+00:00",
  "frame_path": "/data/frames/42.jpg"
}
```

Правила разбора:

- не-JSON, не объект, нечисловой `camera_id`, неизвестный `type` → сообщение отбрасывается;
- `zone_id` можно не передавать; нечисловой `zone_id` заменяется на `null`, сообщение не отбрасывается;
- пустой `track_id` становится `"unknown"`;
- `frame_path` или запасное поле `frame_url`; не строка → `null`;
- `timestamp` — ISO-8601, суффикс `Z` принимается. Битая или пустая метка заменяется на `datetime.now(UTC)`.

Схема воркера (только в `schemas.cpython-313.pyc`, исходника нет) описывает `ViolationEvent` полями `camera_id`, `track_id`, `type`, `timestamp` и метод `to_json()`. `zone_id` и `frame_path` в этой схеме не объявлены. Бэкенд их принимает, если продюсер добавит.

Продюсера в репозитории нет. Потребитель забирает элемент слева (`BLPOP`).

### 5.2. Дедупликация и время в зоне

Класс `DedupGate`. Состояние в памяти процесса, не в Redis и не в БД. Перезапуск API обнуляет гейт: тот же трек может породить новую запись.

Ключ:

```text
(camera_id, zone_id, type.value, track_id)
```

`zone_id is None` — отдельный ключ от зоны `7`. Разные типы по одному треку — разные ключи.

Часы гейта — `time.monotonic()` на момент обработки, не поле `timestamp` сообщения.

Пороги читаются один раз в конструкторе `EventProcessor` из `app_config.thresholds`, иначе константы 3 и 30:

- `zone_stay_seconds` — сколько секунд ключ должен непрерывно наблюдаться;
- `presence_ttl_seconds` — сколько секунд без сообщений ключ считается ушедшим. После этого ключ удаляется из `_first_seen`, `_last_seen` и `_emitted`, и цикл можно начать заново.

Логика `observe` (её же фиксируют тесты):

```python
def observe(self, key, now) -> bool:
    self._purge(now)  # last_seen старше ttl_seconds → забыть ключ
    if key in self._emitted:
        self._last_seen[key] = now
        return False  # нарушение уже создано, пока ключ жив
    if key not in self._first_seen:
        self._first_seen[key] = now
        self._last_seen[key] = now
        return False  # первое наблюдение никогда не создаёт запись
    self._last_seen[key] = now
    return (now - self._first_seen[key]) >= self.stay_seconds
```

Следствия:

1. Одного сообщения недостаточно даже при `zone_stay_seconds = 0`. Нужно минимум два наблюдения одного ключа.
2. Пример при пороге 3 с и TTL 30 с. Сообщения на monotonic `0.0` и `2.9` — записи нет. Сообщение на `3.0` — `observe` возвращает `True`, после успешного commit ключ помечается emitted. Сообщения на `4.0` и `10.0` запись не создают. Если следующее сообщение приходит на `35.0`, а последнее `last_seen` было `4.0` (`35 - 4 > 30`), ключ стирается и это сообщение считается первым заходом (`False`). Следующее на `38.0` снова проходит порог.
3. `ttl_seconds <= 0` отключает purge: ключ живёт до рестарта процесса.
4. Если commit падает, `reset(key)` стирает ключ, следующее сообщение начинает отсчёт заново.
5. Если камера или зона невалидны, гейт не сбрасывается и не помечается emitted: следующий пакет с тем же ключом снова попытается сохранить.

Проверки «человек внутри полигона», «нет каски», «допуск лица» бэкенд не делает. Он доверяет `type` из очереди. `check_type` зоны и `config` камеры на этом пути не участвуют.

Перед записью: камера должна существовать; если `zone_id` задан, зона должна существовать и принадлежать этой камере. Иначе событие отклоняется без записи.

Успешная запись:

```python
Violation(
    camera_id=...,
    zone_id=...,          # может быть None
    track_id=...,
    type=...,             # no_pre | zone_entry | unauthorized
    timestamp=...,        # из сообщения
    frame_path=...,
    # face_id не задаётся
    # identity_status остаётся not_applicable
    # status остаётся open
)
```

Затем для каждого оператора камеры создаётся `Alert(channel="email", status="pending")`. Получатели: `User.role == operator`, строка в `operator_camera`, адрес `email or login`, порядок сохранён, дубли убраны. Администратор письмо не получает, даже если он есть в `operator_camera`. Если операторов нет, нарушение всё равно сохраняется, алертов нет.

`mark_emitted` вызывается после commit и до SMTP. Сбой почты повторную запись нарушения не создаёт.

После почты в WebSocket уходит:

```json
{
  "id": 10,
  "camera_id": 1,
  "zone_id": 7,
  "track_id": "42",
  "type": "no_pre",
  "timestamp": "2026-10-27T20:00:03+00:00",
  "frame_path": "/data/frames/42.jpg",
  "face_id": null,
  "identity_status": "not_applicable",
  "status": "open"
}
```

Поля `admitted`, `camera_name`, `zone_name` в сокет не кладутся.

Тесты: `backend/tests/test_event_handler.py`, `python -m unittest`. Покрыты разбор JSON и `DedupGate`. БД, SMTP и Redis не поднимаются.

---

## 6. Оповещения

Файл `backend/app/services/notification_service.py`.

Письмо (`EmailMessage`):

- `From` = `SMTP_FROM`
- `To` = адрес алерта
- `Subject` = `Нарушение «{type}» (камера {camera_id})`
- тело — текст: тип, камера, зона (`-`, если нет), track, время ISO, строка `Кадр: {frame_path}`, если путь есть

Вложение:

- локальный путь читается `Path.read_bytes()`;
- `http`/`https` качается `urllib.request.urlopen` с таймаутом 10 с;
- имя файла — последний сегмент пути, иначе `frame.jpg`;
- MIME по расширению, иначе `image/jpeg`;
- ошибка чтения кадра не отменяет письмо: уходит текст без вложения.

SMTP: при `SMTP_USE_SSL` — `SMTP_SSL`, иначе `SMTP` и при `SMTP_USE_TLS` — `starttls`. Логин только если `SMTP_USERNAME` непустой. Таймаут сокета равен дедлайну доставки.

Доставка идёт в пуле из 4 потоков `smtp-sender`. `send_email_with_deadline` ждёт `future.result(timeout=ALERT_DELIVERY_TIMEOUT_SECONDS)`. Исключение и `TimeoutError` становятся `NotificationError`. Поток SMTP при таймауте не убивается: ожидание API закончилось, сокет может ещё завершиться.

Статусы в `event_handler._deliver_alerts`:

| Исход | `alerts.status` | `sent_at` |
| --- | --- | --- |
| строка только что вставлена | `pending` | `NULL` |
| `send_email_with_deadline` вернулся | `sent` | текущий UTC |
| `NotificationError` (таймаут или ошибка SMTP) | `failed` | `NULL` |

В лог пишется `error`: «Оповещение {recipient} по нарушению {id} не доставлено». Отдельного алерта администратору о срыве срока нет. Промежуточного статуса между `pending` и `failed` нет. Успешные и неуспешные алерты коммитятся одним `db.commit()` в конце цикла по получателям. Исключение вне `NotificationError` откатывает сессию и логируется, уже отправленные письма в БД могут остаться `pending`.

---

## 7. WebSocket

`WS /api/v1/ws/violations`.

Авторизация, до `manager.connect`:

1. Сокет принимается (`accept`).
2. Токен берётся из query `?token=<access_token>`. Если его нет — из заголовка `Authorization: Bearer ...`.
3. Нет токена, токен не access, пользователь не найден, JWT битый — `close(1008)`.
4. `assigned_camera_ids` снимается один раз и запоминается на соединении. Админ: `None` (все камеры). Оператор: множество id, может быть пустым.
5. Дальше цикл только читает входящие кадры и игнорирует их. Назначение камер после подключения не обновляется. Истечение access на уже открытом сокете не проверяется.

Рассылка из обработчика очереди, не из сырого Redis:

```json
{
  "type": "violation",
  "data": {
    "id": 10,
    "camera_id": 1,
    "zone_id": 7,
    "track_id": "42",
    "type": "no_pre",
    "timestamp": "2026-10-27T20:00:03+00:00",
    "frame_path": "/data/frames/42.jpg",
    "face_id": null,
    "identity_status": "not_applicable",
    "status": "open"
  }
}
```

Фильтр: если у сокета множество камер не `None` и `camera_id` в него не входит, кадр не шлётся. Ошибка отправки удаляет сокет из реестра. Heartbeat нет.

`stream_redis_violations` рассылал бы сырой JSON очереди тем же фильтром, но сейчас не запущен.

---

## 8. Ограничения и заделы

Заделы, которые прямо написаны в коде:

- `faces.embedding` — JSONB «до следующей фазы», комментарий про pgvector.
- `cameras.worker_id` — nullable int без FK, «при необходимости навесим FK».
- `Alert.channel` — комментарий перечисляет email, telegram, sms. Реализован только `email`.
- `worker/core/__init__.py` обещает схемы данных. `schemas.py` не закоммичен, есть только `schemas.cpython-313.pyc` с моделями `Detection` (`track_id`, `class_name`, `bbox`, `confidence`, `attributes`) и `ViolationEvent`.
- `worker/core/config.py` ждёт `worker/config.yaml` с `analyze_every_n: 30` и `fps: 30`. Файла нет, срабатывают дефолты. Классы детекции воркера: `person`, `helmet`, `safety_vest`.
- `config.yaml` бэкенда содержит пустые `ppe_classes` и `cameras`.
- `AuditLog` готов и нигде не заполняется.
- `stream_redis_violations` — второй потребитель той же очереди, не подключённый к lifespan.
- README описывает фазу 5 как текущий этап и ссылается на отсутствующий `.env.example`.

Чего в коде нет, хотя модели или ТЗ это подразумевают:

- чтение RTSP, детекция, трекинг, проверка полигона, публикация в Redis;
- отдача живого потока (HLS, MJPEG, WebRTC, прокси RTSP) и «последнего кадра»;
- CRUD пользователей, лиц, допусков зоны, назначений `operator_camera`;
- эндпоинты воркеров, статуса камеры, дневного CSV;
- запись `face_id` / `identity_status` из события;
- применение `check_type`, `active` и `cameras.config` в обработчике;
- копирование кадра `false_alarm` в отдельный каталог;
- rate limit, security-заголовки, TLS (его нет внутри приложения);
- тесты API.

Видео сейчас: API хранит и отдаёт строку `frame_path`. Показать картинку или поток этот сервис не умеет. Сид может создать камеру с `synthetic://camera-{id}` и `status=online`, чтобы обработчик не отклонял события несуществующей камеры. Такой URL через `POST /cameras` не пройдёт.
