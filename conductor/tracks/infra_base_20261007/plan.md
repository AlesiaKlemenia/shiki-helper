# Implementation Plan: Инфраструктурный каркас, База Данных и Redis

**Track ID:** `infra_base_20261007`
**Type:** MVP / Bootstrap
**Status:** New

---

## Phase 1: Структура проекта, конфигурация и зависимости

- [ ] Task: Создать иерархию директорий и файлов проекта
  - [ ] Создать все директории: `app/`, `app/core/`, `app/clients/`, `app/db/`, `app/db/repositories/`, `app/services/`, `app/scheduler/`, `app/bot/`, `app/bot/dialogs/`, `app/bot/handlers/`, `app/bot/middlewares/`, `tests/`, `migrations/`
  - [ ] Создать пустые `__init__.py` во всех пакетах
- [ ] Task: Создать `requirements.txt` со всеми зависимостями
  - [ ] aiogram 3.x, aiogram-dialog
  - [ ] sqlalchemy[asyncio], asyncpg, aiosqlite, alembic
  - [ ] redis, aioredis (для aiogram RedisStorage)
  - [ ] pydantic-settings, python-dotenv
  - [ ] httpx, aiolimiter
  - [ ] google-auth, google-auth-oauthlib, google-api-python-client
  - [ ] cryptography
  - [ ] apscheduler
  - [ ] pytest, pytest-asyncio, pytest-cov, pytest-mock, ruff, mypy
- [ ] Task: Создать `app/config.py` (Pydantic BaseSettings)
  - [ ] Написать тест `tests/test_config.py` (TDD: тест наличия всех полей)
  - [ ] Реализовать `Settings` класс с полным набором полей
- [ ] Task: Создать `.env.example`, `Dockerfile` и `docker-compose.yml`
  - [ ] `.env.example` со всеми переменными
  - [ ] `Dockerfile` (python:3.11-slim, multi-stage)
  - [ ] `docker-compose.yml` (сервисы `bot` + `redis:7-alpine`)
- [ ] Task: Phase 1 Verification & Checkpoint (Refer to workflow.md)

## Phase 2: Структурированное логирование и шифрование токенов

- [ ] Task: Реализовать `app/core/logger.py`
  - [ ] Написать тест `tests/test_logger.py` (TDD: тест настройки уровня логирования)
  - [ ] Реализовать `setup_logging(level: str = "INFO")` функцию
- [ ] Task: Реализовать `app/core/security.py` (Fernet encryption)
  - [ ] Написать тесты `tests/test_security.py` (TDD):
    - [ ] Тест успешного шифрования и расшифровки токена
    - [ ] Тест ошибки расшифровки при неверном ключе (возвращает None)
    - [ ] Тест ошибки расшифровки при испорченных данных (возвращает None)
  - [ ] Реализовать `TokenEncryptor` класс с методами `encrypt()` и `decrypt()`
- [ ] Task: Phase 2 Verification & Checkpoint (Refer to workflow.md)

## Phase 3: Async подключение к БД (SQLAlchemy session)

- [ ] Task: Реализовать `app/db/session.py`
  - [ ] Написать тесты `tests/test_db_session.py` (TDD):
    - [ ] Тест создания async engine для SQLite URL
    - [ ] Тест создания async engine для PostgreSQL URL
    - [ ] Тест работы контекстного менеджера `get_session()`
  - [ ] Реализовать `async_engine`, `AsyncSessionLocal`, `get_session()` контекстный менеджер
  - [ ] Поддержка обоих диалектов через `DATABASE_URL` схему
- [ ] Task: Phase 3 Verification & Checkpoint (Refer to workflow.md)

## Phase 4: Модели данных (SQLAlchemy 2.0)

- [ ] Task: Реализовать `app/db/models.py`
  - [ ] Написать тесты `tests/test_models.py` (TDD):
    - [ ] Тест инициализации модели `User` с дефолтными значениями
    - [ ] Тест инициализации модели `GoogleCredentials` с FK
    - [ ] Тест инициализации модели `TrackedTitle` с дефолтными значениями
    - [ ] Тест наличия всех колонок в `__table__.columns`
  - [ ] Реализовать `Base`, `User`, `GoogleCredentials`, `TrackedTitle`
  - [ ] Все поля с типами, дефолтами и nullable согласно спецификации
- [ ] Task: Настроить Alembic (`alembic.ini` + `migrations/env.py`)
  - [ ] Инициализировать Alembic в режиме async
  - [ ] Настроить `env.py` для async миграций (asyncpg/aiosqlite)
  - [ ] Сгенерировать первую миграцию `init_tables` и убедиться в корректности SQL
- [ ] Task: Phase 4 Verification & Checkpoint (Refer to workflow.md)

## Phase 5: Redis FSM Storage с graceful degradation

- [ ] Task: Реализовать логику выбора хранилища FSM
  - [ ] Написать тесты `tests/test_storage.py` (TDD):
    - [ ] Тест: при доступном Redis возвращается `RedisStorage`
    - [ ] Тест: при недоступном Redis возвращается `MemoryStorage` и логируется warning
  - [ ] Реализовать функцию `create_storage(redis_url: str | None) -> BaseStorage`
  - [ ] Использовать PING-проверку перед подключением
- [ ] Task: Phase 5 Verification & Checkpoint (Refer to workflow.md)

## Phase 6: Shadow DB / Sandbox mode

- [ ] Task: Реализовать `DynamicSessionMaker` с ContextVar
  - [ ] Написать тесты `tests/test_sandbox.py` (TDD):
    - [ ] Тест: `get_session()` без sandbox возвращает боевую сессию
    - [ ] Тест: после `enable_sandbox()` возвращает in-memory SQLite сессию
    - [ ] Тест: после `disable_sandbox()` снова возвращает боевую сессию
    - [ ] Тест: sandbox-сессии разных пользователей изолированы
  - [ ] Реализовать `DynamicSessionMaker` с `ContextVar[Optional[AsyncSession]]`
  - [ ] Реализовать методы `enable_sandbox(user_id)`, `disable_sandbox()`, `get_session()`
- [ ] Task: Phase 6 Verification & Checkpoint (Refer to workflow.md)

## Phase 7: Точка входа и итоговая проверка

- [ ] Task: Создать минимальный `app/main.py`
  - [ ] Инициализация бота с `Bot(token=settings.BOT_TOKEN)`
  - [ ] Выбор хранилища (FSM storage) через `create_storage()`
  - [ ] Вызов `setup_logging()` при старте
  - [ ] Заглушка `async def main()` с `dp.start_polling(bot)`
- [ ] Task: Создать `.gitignore` (venv, __pycache__, .env, *.pyc, .coverage)
- [ ] Task: Phase 7 Verification & Checkpoint — итоговая проверка всего этапа
  - [ ] `pytest tests/ --cov=app --cov-fail-under=80` — зелёный
  - [ ] `ruff check app/ tests/` — без ошибок
  - [ ] `mypy app/` — без ошибок типов
  - [ ] `alembic upgrade head` — успешно применяет миграцию
