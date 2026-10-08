# Implementation Plan: Инфраструктурный каркас, База Данных и Redis

**Track ID:** `infra_base_20261007`
**Type:** MVP / Bootstrap
**Status:** Complete

---

## Phase 1: Структура проекта, конфигурация и зависимости

- [x] Task: Создать иерархию директорий и файлов проекта
  - [x] Создать все директории: `app/`, `app/core/`, `app/clients/`, `app/db/`, `app/db/repositories/`, `app/services/`, `app/scheduler/`, `app/bot/`, `app/bot/dialogs/`, `app/bot/handlers/`, `app/bot/middlewares/`, `tests/`, `migrations/`
  - [x] Создать пустые `__init__.py` во всех пакетах
- [x] Task: Создать `requirements.txt` со всеми зависимостями
  - [x] aiogram 3.x, aiogram-dialog
  - [x] sqlalchemy[asyncio], asyncpg, aiosqlite, alembic
  - [x] redis, aioredis (для aiogram RedisStorage)
  - [x] pydantic-settings, python-dotenv
  - [x] httpx, aiolimiter
  - [x] google-auth, google-auth-oauthlib, google-api-python-client
  - [x] cryptography
  - [x] apscheduler
  - [x] pytest, pytest-asyncio, pytest-cov, pytest-mock, ruff, mypy
- [x] Task: Создать `app/config.py` (Pydantic BaseSettings)
  - [x] Написать тест `tests/test_config.py` (TDD: тест наличия всех полей)
  - [x] Реализовать `Settings` класс с полным набором полей
- [x] Task: Создать `.env.example`, `Dockerfile` и `docker-compose.yml`
  - [x] `.env.example` со всеми переменными
  - [x] `Dockerfile` (python:3.11-slim, multi-stage)
  - [x] `docker-compose.yml` (сервисы `bot` + `redis:7-alpine`)
- [x] Task: Phase 1 Verification & Checkpoint (Refer to workflow.md)

## Phase 2: Структурированное логирование и шифрование токенов

- [x] Task: Реализовать `app/core/logger.py`
  - [x] Написать тест `tests/test_logger.py` (TDD: тест настройки уровня логирования)
  - [x] Реализовать `setup_logging(level: str = "INFO")` функцию
- [x] Task: Реализовать `app/core/security.py` (Fernet encryption)
  - [x] Написать тесты `tests/test_security.py` (TDD):
    - [x] Тест успешного шифрования и расшифровки токена
    - [x] Тест ошибки расшифровки при неверном ключе (возвращает None)
    - [x] Тест ошибки расшифровки при испорченных данных (возвращает None)
  - [x] Реализовать `TokenEncryptor` класс с методами `encrypt()` и `decrypt()`
- [x] Task: Phase 2 Verification & Checkpoint (Refer to workflow.md)

## Phase 3: Async подключение к БД (SQLAlchemy session)

- [x] Task: Реализовать `app/db/session.py`
  - [x] Написать тесты `tests/test_db_session.py` (TDD):
    - [x] Тест создания async engine для SQLite URL
    - [x] Тест создания async engine для PostgreSQL URL
    - [x] Тест работы контекстного менеджера `get_session()`
  - [x] Реализовать `async_engine`, `AsyncSessionLocal`, `get_session()` контекстный менеджер
  - [x] Поддержка обоих диалектов через `DATABASE_URL` схему
- [x] Task: Phase 3 Verification & Checkpoint (Refer to workflow.md)

## Phase 4: Модели данных (SQLAlchemy 2.0)

- [x] Task: Реализовать `app/db/models.py`
  - [x] Написать тесты `tests/test_models.py` (TDD):
    - [x] Тест инициализации модели `User` с дефолтными значениями
    - [x] Тест инициализации модели `GoogleCredentials` с FK
    - [x] Тест инициализации модели `TrackedTitle` с дефолтными значениями
    - [x] Тест наличия всех колонок в `__table__.columns`
  - [x] Реализовать `Base`, `User`, `GoogleCredentials`, `TrackedTitle`
  - [x] Все поля с типами, дефолтами и nullable согласно спецификации
- [x] Task: Настроить Alembic (`alembic.ini` + `migrations/env.py`)
  - [x] Инициализировать Alembic в режиме async
  - [x] Настроить `env.py` для async миграций (asyncpg/aiosqlite)
  - [x] Сгенерировать первую миграцию `init_tables` и убедиться в корректности SQL
- [x] Task: Phase 4 Verification & Checkpoint (Refer to workflow.md)

## Phase 5: Redis FSM Storage с graceful degradation

- [x] Task: Реализовать логику выбора хранилища FSM
  - [x] Написать тесты `tests/test_storage.py` (TDD):
    - [x] Тест: при доступном Redis возвращается `RedisStorage`
    - [x] Тест: при недоступном Redis возвращается `MemoryStorage` и логируется warning
  - [x] Реализовать функцию `create_storage(redis_url: str | None) -> BaseStorage`
  - [x] Использовать PING-проверку перед подключением
- [x] Task: Phase 5 Verification & Checkpoint (Refer to workflow.md)

## Phase 6: Shadow DB / Sandbox mode

- [x] Task: Реализовать `DynamicSessionMaker` с ContextVar
  - [x] Написать тесты `tests/test_sandbox.py` (TDD):
    - [x] Тест: `get_session()` без sandbox возвращает боевую сессию
    - [x] Тест: после `enable_sandbox()` возвращает in-memory SQLite сессию
    - [x] Тест: после `disable_sandbox()` снова возвращает боевую сессию
    - [x] Тест: sandbox-сессии разных пользователей изолированы
  - [x] Реализовать `DynamicSessionMaker` с `ContextVar[Optional[AsyncSession]]`
  - [x] Реализовать методы `enable_sandbox(user_id)`, `disable_sandbox()`, `get_session()`
- [x] Task: Phase 6 Verification & Checkpoint (Refer to workflow.md)

## Phase 7: Точка входа и итоговая проверка

- [x] Task: Создать минимальный `app/main.py`
  - [x] Инициализация бота с `Bot(token=settings.BOT_TOKEN)`
  - [x] Выбор хранилища (FSM storage) через `create_storage()`
  - [x] Вызов `setup_logging()` при старте
  - [x] Заглушка `async def main()` с `dp.start_polling(bot)`
- [x] Task: Создать `.gitignore` (venv, __pycache__, .env, *.pyc, .coverage)
- [x] Task: Phase 7 Verification & Checkpoint — итоговая проверка всего этапа
  - [x] `pytest tests/` — 53 теста зелёные
  - [x] `ruff check app/ tests/` — 0 ошибок
  - [x] `mypy app/` — 0 ошибок типов
  - [x] `alembic upgrade head` — успешно применяет миграцию 0001_initial

