# Video Surveillance Platform — CV Worker

Отдельный сервис (CV-воркер) платформы видеонаблюдения.

## Фаза 3: ядро CV
- Базовый абстрактный класс `DetectionModule` (ABC).
- Чтение RTSP-потока через OpenCV.
- Анализ с частотой **1 кадр в секунду** (каждый 30-й кадр при 30 fps).
- Заглушка `MockModule` (без Ultralytics), генерирующая событие «человек без СИЗ» (тип `no_pre`).
- Публикация событий в очередь Redis `violations_queue`.

## Классы детекции (из ТЗ)
`person`, `helmet` (каска), `safety_vest` (жилет) — `worker.core.enums.DetectionClass`.

## Структура
```
worker/
  main.py            # точка входа (CLI)
  core/
    config.py        # настройки: .env + config.yaml
    enums.py         # DetectionClass, ViolationType
    schemas.py       # Detection, ViolationEvent (pydantic)
  modules/
    base.py          # DetectionModule (ABC)
    mock.py          # MockModule (заглушка)
  stream.py          # RTSPFrameSource (OpenCV)
  publisher.py       # RedisPublisher (очередь violations_queue)
  pipeline.py        # AnalysisPipeline (оркестрация)
  tests/
    test_pipeline.py # юнит-тесты
```

## Установка
```bash
cd worker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заполнить RTSP_URL, CAMERA_ID, REDIS_URL
```

## Запуск
```bash
# из корня репозитория
python -m worker.main --rtsp-url "rtsp://user:pass@host:554/stream" --camera-id 1
```
Значения по умолчанию читаются из `.env` и `config.yaml`.

## Формат сообщения (очередь `violations_queue`)
```json
{
  "camera_id": "1",
  "track_id": "42",
  "type": "no_pre",
  "timestamp": "2026-10-27T20:00:00+00:00"
}
```

## Тесты
```bash
python -m unittest worker.tests.test_pipeline -v
```

## Дальнейшие фазы
`MockModule` будет заменён модулями на базе Ultralytics (`PersonModule`,
`HelmetModule`, `SafetyVestModule`), наследующими `DetectionModule`.