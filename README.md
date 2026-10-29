# Платформа видеонаблюдения

Сервис из трёх частей: CV-воркер читает кадры, кладёт события в Redis, backend на FastAPI пишет нарушения в PostgreSQL и отдаёт их API и WebSocket, React-интерфейс показывает ленту и дашборд.

В коде сервисы называются Video Surveillance Platform (`docker-compose.yml`, заголовок страницы `frontend/index.html`). В боковой панели интерфейса подпись «ЧКПЗ · Видеонаблюдение». Других сведений о площадке, камерах или показателях в репозитории нет.

Детекция в текущем коде — заглушка `MockModule`, без нейросети. Модулей Ultralytics в репозитории нет. Файл `train.py` в корне пустой; что он должен делать, в коде не описано.

## Состав репозитория

```
.
├── docker-compose.yml    # db, redis, backend, worker-1, worker-2, frontend
├── .env.example          # шаблон окружения для Docker Compose
├── train.py              # пустой файл
├── backend/              # FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis
├── worker/               # чтение кадров, MockModule, публикация в Redis
└── frontend/             # React + Vite + TypeScript, в контейнере — Nginx
```

Каталоги зависимостей и локальные секреты в репозиторий не входят: их исключают `.gitignore` в `backend/`, `worker/` и `frontend/`.

### Backend

`backend/app/main.py` — приложение FastAPI. Роутеры: аутентификация, камеры, зоны, нарушения, WebSocket. Кадры нарушений раздаются как статика с `/api/v1/frames`, если каталог кадров удалось создать.

При старте контейнера `backend/entrypoint.sh` выполняет, по порядку:

```sh
alembic upgrade head
python -m app.seed
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Образ: `python:3.13-slim` (`backend/Dockerfile`).

Модели БД: пользователи, камеры, зоны, нарушения, оповещения (`alerts`), связь оператора с камерой, лица, разрешения на зону, журнал аудита. Код создаёт строки только для камер и администратора из сидинга и для нарушений с оповещениями из очереди. Записи лиц, разрешений и аудита приложение само не пишет; API для них нет.

### Worker

Пакет `worker/`. Точка входа — `python -m worker.main` (`worker/Dockerfile`, `CMD`).

- `stream.py` — RTSP через OpenCV. Если `RTSP_URL` пуст или поток не открылся, используется `SyntheticFrameSource`: чёрный кадр 640×480, по умолчанию 30 кадров/с.
- `modules/mock.py` — `MockModule`. Реальной детекции нет: не чаще одного раза в секунду публикуется событие `no_pre` (в атрибутах детекции каска и жилет отсутствуют). Один `track_id` держится 10 секунд, затем выдаётся следующий.
- `pipeline.py` — анализирует каждый N-й кадр. По умолчанию N = 30 (`worker/config.yaml`, ключ `analyze_every_n`). При 30 fps это один анализ в секунду. Кадр события пишется в JPEG; если сохранить не удалось, событие всё равно уходит в очередь, без `frame_path`.
- `publisher.py` — `RPUSH` JSON в очередь Redis.

Классы `person`, `helmet`, `safety_vest` объявлены в `worker/core/enums.py` и перечислены в `worker/config.yaml`. Рабочий модуль сейчас один — `MockModule` — и он порождает только тип `no_pre`. Типы `zone_entry` и `unauthorized` есть в перечислениях backend и worker, но текущий воркер их не отправляет.

Сообщение очереди (поля из `worker/core/schemas.py`): `camera_id`, `track_id`, `type`, `timestamp`. Поле `frame_path` добавляется, если кадр сохранился. `zone_id` схема воркера не заполняет.

### Frontend

React 18, Vite 6, TypeScript, Tailwind CSS 4. Скрипты в `frontend/package.json`:

- `npm run dev` — Vite
- `npm run build` — `tsc && vite build`
- `npm run preview` — просмотр сборки

`frontend/vite.config.ts`: порт 3000, прокси `/api` (включая WebSocket) на `http://localhost:8000`.

Образ (`frontend/Dockerfile`): сборка на `node:20-alpine` (`npm install`, затем `npm run build`), раздача через `nginx:1.27-alpine`. `frontend/nginx.conf` отдаёт SPA и проксирует `/api/` на `http://backend:8000`. Поле `engines` в `package.json` нет: какая версия Node нужна вне Docker, в репозитории не зафиксировано. Образ сборки — Node 20.

Маршруты (`frontend/src/App.tsx`):

| Путь | Что делает код |
| --- | --- |
| `/login` | вход через `POST /api/v1/auth/login` |
| `/` | редирект на `/timeline` |
| `/timeline` | лента: `GET /api/v1/violations?limit=200`, WebSocket, фильтры на клиенте, подтверждение и ложная тревога |
| `/dashboard` | число камер, открытые нарушения и события за сегодня из тех же API; столбцы за последние 12 часов; кольцо по статусам `open` / `confirmed` / `false_alarm` |
| `/cameras`, `/live`, `/settings`, `/logs` | заголовок и подпись, без запросов к API и без видео |

Подпись «События по часам» говорит «за выбранный период», но период в коде фиксирован: 12 часов до текущего часа. Отдельного выбора периода нет.

## Как это связано

1. Воркер публикует JSON в Redis, очередь `violations_queue` (имя берётся из окружения, по умолчанию такое).
2. `app.services.event_handler` читает очередь всё время жизни процесса FastAPI.
3. Событие отбрасывается, если JSON неразобран, тип неизвестен или камеры с таким `camera_id` нет в БД. Если передан `zone_id`, зона должна существовать и принадлежать этой камере. Воркер `zone_id` сейчас не передаёт, поэтому проверка зоны для его сообщений не выполняется.
4. Ключ дедупликации: камера, зона, тип, `track_id`. Первое наблюдение ключа нарушение не создаёт. Запись создаётся, когда ключ непрерывно наблюдается не меньше `thresholds.zone_stay_seconds` из `backend/config.yaml` (в файле — 3 секунды). Повтор той же ключ-комбинации новую строку не создаёт, пока по ключу не прошло `thresholds.presence_ttl_seconds` без событий (в файле — 30 секунд).
5. Новая строка пишется в `violations`. Для операторов, привязанных к камере таблицей `operator_camera` и с ролью `operator`, создаются `alerts` со статусом `pending` и вызывается SMTP. Адрес получателя — `email`, а если его нет, то `login`. Срок попытки — `ALERT_DELIVERY_TIMEOUT_SECONDS`. При ошибке алерт помечается `failed`. Если таких операторов нет, нарушение сохраняется, письмо не отправляется. Сидинг операторов и связей `operator_camera` не создаёт, отдельного API пользователей нет.
6. То же нарушение уходит подключённым WebSocket-клиентам. Оператор получает события только по назначенным камерам.

Роли пользователей: `admin` и `operator`. Оператор видит только камеры из `operator_camera`. Создание, изменение и удаление камер и зон — у `admin`.

В ленте по умолчанию скрыты «допущенные» нарушения: `identity_status = identified` и есть строка в `zone_permissions` для этой пары лицо–зона. Текущий воркер лицо не определяет и `identity_status` не присылает, поэтому этот фильтр на его событиях не срабатывает. Параметр `include_admitted=true` показывает и такие строки, если они есть в БД.

## Запуск в Docker Compose

Из корня репозитория, как в комментарии `docker-compose.yml`:

```bash
cp .env.example .env
docker compose up --build
```

Имя проекта Compose: `video-surveillance`. Сервисы:

| Сервис | Образ / сборка | Порт на хосте |
| --- | --- | --- |
| `db` | `postgres:16-alpine`, контейнер `vs-db` | `${POSTGRES_PORT:-5433}` → 5432 |
| `redis` | `redis:7-alpine`, AOF, контейнер `vs-redis` | `${REDIS_PORT:-6379}` → 6379 |
| `backend` | сборка `./backend`, контейнер `vs-backend` | `${BACKEND_PORT:-8000}` → 8000 |
| `worker-1` | сборка `./worker`, контейнер `vs-worker-1` | наружу не публикуется, `CAMERA_ID=1` |
| `worker-2` | сборка `./worker`, контейнер `vs-worker-2` | наружу не публикуется, `CAMERA_ID=2` |
| `frontend` | сборка `./frontend`, контейнер `vs-frontend` | `${FRONTEND_PORT:-3000}` → 80 |

Общие тома: `postgres_data`, `redis_data`, `frames_data` (смонтирован в `/app/frames` у backend и обоих воркеров).

После старта интерфейс открывается на порту `FRONTEND_PORT` (в шаблоне это 3000): `http://localhost:3000`. Запросы браузера к `/api` идут на Nginx фронтенда, тот проксирует их на backend. Напрямую API слушает порт `BACKEND_PORT` (в шаблоне 8000): `GET /health` возвращает `{"status": "ok"}`. Страницы `/docs` и `/redoc` FastAPI в коде не отключены, они доступны на порту backend, не через Nginx (тот проксирует только префикс `/api/`).

Оба воркера читают один и тот же `RTSP_URL` из `.env`. Отдельной переменной для второй камеры в `docker-compose.yml` нет. `CAMERA_ID` из корневого `.env` на эти сервисы не действует: Compose задаёт `"1"` и `"2"` явно. Если `RTSP_URL` пуст, оба воркера пишут события с чёрного кадра.

Сидинг при старте backend (`backend/app/seed.py`), если переменные заданы и строк ещё нет:

- камеры с id из `SEED_CAMERA_IDS`: имя «Камера {id}», `rtsp_url` вида `synthetic://camera-{id}`, статус `online`;
- пользователь с ролью `admin`, если `SEED_ADMIN_LOGIN` не пустой.

Без камеры в БД обработчик отклоняет сообщения воркера. Логин и пароль администратора задаются только в вашем `.env` по шаблону `.env.example`. В этот файл их копировать не нужно: `.env` не коммитится.

## Локальный запуск без Compose

Нужны свои PostgreSQL и Redis. Команды ниже взяты из `backend/README.md`, `worker/README.md`, `frontend/package.json` и `frontend/vite.config.ts`. Образы Docker фиксируют Python 3.13; локальные README версию интерпретатора не задают.

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Ревизии уже лежат в `backend/alembic/versions/`. `backend/README.md` дополнительно показывает, как сгенерировать новую ревизию:

```bash
alembic revision --autogenerate -m "init db schema"
```

Повторять эту команду для уже существующих ревизий не требуется. Контейнер вызывает только `alembic upgrade head`.

Тесты обработчика (из каталога `backend`, строка в `backend/tests/test_event_handler.py`):

```bash
python -m unittest tests.test_event_handler -v
```

### Worker

Установка — из каталога `worker`, запуск модуля — из корня репозитория (так написано в `worker/README.md`; пакет называется `worker`, поэтому корень должен быть в `PYTHONPATH`):

```bash
cd worker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cd ..
python -m worker.main --rtsp-url "rtsp://user:pass@host:554/stream" --camera-id 1
```

Аргументы `--rtsp-url`, `--camera-id` и `--analyze-every-n` необязательны: без них берутся `.env` воркера и `worker/config.yaml`. Пустой `RTSP_URL` включает чёрный кадр, процесс не завершается.

Тесты пайплайна из корня репозитория:

```bash
python -m unittest worker.tests.test_pipeline -v
```

Образ воркера ставит библиотеки OpenCV (`libgl1`, `libglib2.0-0`, `libsm6`, `libxext6`, `libxrender1`). Локальный README системные пакеты не перечисляет.

### Frontend

Отдельного README у frontend нет.

```bash
cd frontend
npm install
npm run dev
```

Интерфейс: `http://localhost:3000`. Backend при этом должен слушать `http://localhost:8000`, иначе прокси `/api` из `vite.config.ts` некуда отправлять запросы. Сборка: `npm run build`, просмотр собранных файлов: `npm run preview`.

## Конфигурация

Секреты и адреса берутся из `.env`, который вы создаёте копией шаблона. В репозитории только шаблоны. Значения из локального `.env` сюда не входят.

| Файл | Кто его читает |
| --- | --- |
| `.env.example` | Docker Compose (`env_file: .env` у backend и воркеров) |
| `backend/.env.example` | локальный backend: pydantic-settings, файл `backend/.env` |
| `worker/.env.example` | локальный воркер: pydantic-settings, файл `worker/.env` |

Подставьте свои значения в скопированный `.env`. Ниже только имена переменных.

Корневой шаблон, группы как в `.env.example`:

- PostgreSQL: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `DATABASE_URL`
- Redis: `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_URL`, `VIOLATIONS_QUEUE`
- JWT: `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`
- SMTP: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_USE_TLS`, `SMTP_USE_SSL`, `ALERT_DELIVERY_TIMEOUT_SECONDS`
- Порты приложения: `DEBUG`, `BACKEND_PORT`, `FRONTEND_PORT`
- Воркер: `RTSP_URL`, `CAMERA_ID`
- Сидинг: `SEED_CAMERA_IDS`, `SEED_ADMIN_LOGIN`, `SEED_ADMIN_PASSWORD`, `SEED_ADMIN_EMAIL`

`backend/.env.example` содержит `DATABASE_URL`, JWT, Redis, SMTP и `DEBUG`. Ключей `SEED_*` и `FRAMES_DIR` в нём нет.

`worker/.env.example` содержит `REDIS_URL`, `VIOLATIONS_QUEUE`, `RTSP_URL`, `CAMERA_ID`.

Что Compose переопределяет поверх файла:

- у backend `DATABASE_URL` собирается как `postgresql+psycopg2://<пользователь>:<пароль>@db:5432/<база>`, `REDIS_URL` — `redis://redis:6379/0`;
- у воркеров `REDIS_URL` тот же, `CAMERA_ID` равен `1` или `2`, `RTSP_URL` берётся из `.env` (пустая строка, если переменной нет);
- порт Postgres на хосте — `POSTGRES_PORT`, внутри сети контейнер слушает 5432. В корневом шаблоне `POSTGRES_PORT` и порт внутри `DATABASE_URL` поэтому разные: шаблон рассчитан на сеть Compose (`хост db`, порт 5432), а не на проброс с хоста.

Несовпадения, которые в коде не сведены к одной инструкции:

- `backend/.env.example` указывает `DATABASE_URL` на `localhost` и порт `5432`. Compose по умолчанию публикует Postgres на порт хоста из `POSTGRES_PORT` (в корневом шаблоне это не 5432). Как подключить локальный backend к контейнеру БД, репозиторий не объясняет: шаблоны надо согласовать самостоятельно.
- `app/seed.py` читает `SEED_*` через `os.getenv`, а не через объект настроек. В контейнере их подставляет `env_file`. При локальном запуске копирование `backend/.env.example` эти переменные не задаёт, и загрузчик настроек не кладёт их в окружение процесса. Без отдельного экспорта сидинг их не увидит.
- `FRAMES_DIR` есть в настройках backend и воркера со значением по умолчанию `/app/frames`, но ни в одном `.env.example` этой переменной нет. В Compose каталог — том `frames_data`. Вне контейнера `/app/frames` может быть недоступен: кадр тогда не сохраняется, событие в очередь всё равно уходит. Backend в этом случае пишет предупреждение и не монтирует раздачу `/api/v1/frames`.

Несекретные пороги — в YAML, не в `.env`:

- `backend/config.yaml`: имя `video-surveillance`, версия `0.1.0`; CORS-origins `http://localhost:3000` и `http://localhost:8080`; `zone_stay_seconds: 3`; `presence_ttl_seconds: 30`. Списки `ppe_classes` и `cameras` пустые. Их загружает `AppConfig`, но остальной код читает только `app`, `cors` и `thresholds`. Порт 8080 в Compose и во frontend не используется.
- `worker/config.yaml`: `analyze_every_n: 30`, `fps: 30`, классы `person`, `helmet`, `safety_vest`. Поле `fps` задаёт ожидаемую частоту в комментарии к N; цикл чтения идёт с частотой источника кадров, отдельного ограничителя по этому полю нет. У синтетического источника своя частота, по умолчанию 30 кадров/с, аргументом CLI она не задаётся.

## HTTP API

Префикс `/api/v1`. Кроме `/health` и `/api/v1/auth/login` с `/api/v1/auth/refresh`, нужен заголовок `Authorization: Bearer <access_token>`. Сроки токенов по умолчанию: access 60 минут, refresh 7 дней (и в коде, и в шаблонах).

- `POST /api/v1/auth/login` — тело `{"login", "password"}`
- `POST /api/v1/auth/refresh` — тело `{"refresh_token"}`
- `GET /health`
- `GET|POST /api/v1/cameras`, `GET|PATCH|DELETE /api/v1/cameras/{id}`
- `GET|POST /api/v1/cameras/{id}/zones`, `GET|PATCH|DELETE /api/v1/cameras/{id}/zones/{zone_id}`
- `GET /api/v1/violations` — фильтры `camera_id`, `zone_id`, `type`, `date_from`, `date_to`, `include_admitted`, `limit` (1…200, по умолчанию 50), `offset`
- `POST /api/v1/violations/{id}/feedback` — `{"decision": "confirmed"}` или `{"decision": "false_alarm"}`; повторно закрытое нарушение не меняется
- `WS /api/v1/ws/violations?token=<access_token>` (или заголовок `Authorization: Bearer ...`)

Интерфейс вызывает вход, список камер, список нарушений с `limit=200`, обратную связь и WebSocket. Остальные методы камер и зон есть в API; страницы «Cameras» и «Live View» ими не пользуются.

Типы нарушений в API и в подписях интерфейса: `no_pre` («Без СИЗ»), `zone_entry` («Вход в зону»), `unauthorized` («Несанкционированный доступ»). Типы проверки зоны в модели: `pre_in_zone`, `zone_only`, `disabled`.
