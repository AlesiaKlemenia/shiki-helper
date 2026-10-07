# Track Specification: Инфраструктурный каркас, База Данных и Redis

## Overview

Этот трек реализует полный инфраструктурный фундамент бота Shiki-Helper: структуру проекта, конфигурацию, подключение к базе данных, Redis FSM storage, модели данных, миграции Alembic и шифрование OAuth-токенов.

## Functional Requirements

### FR-1: Структура проекта
- Создать полную иерархию директорий и пустых `__init__.py` согласно структуре из `PLAN.md`.
- Файлы: `app/main.py`, `app/config.py`, `app/core/logger.py`, `app/core/security.py`, `app/db/session.py`, `app/db/models.py`, `app/db/repositories/user_repo.py`, `app/db/repositories/title_repo.py`, `app/clients/__init__.py`, `app/services/__init__.py`, `app/scheduler/__init__.py`, `app/bot/__init__.py`.

### FR-2: Конфигурация и окружение
- `app/config.py`: Pydantic `BaseSettings` с полями: `BOT_TOKEN`, `DATABASE_URL`, `REDIS_URL` (optional), `ENCRYPTION_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `ADMIN_TELEGRAM_ID`.
- `.env.example`: шаблон со всеми переменными с пустыми или дефолтными значениями.
- `requirements.txt`: все зависимости с версиями.
- `Dockerfile`: multi-stage build для Python 3.11-slim.
- `docker-compose.yml`: сервисы `bot` (build) и `redis` (redis:7-alpine), с `volumes` для Redis.

### FR-3: Async подключение к БД (SQLAlchemy)
- `app/db/session.py`: `async_engine` через `create_async_engine`, `AsyncSessionLocal` через `async_sessionmaker`.
- Поддержка PostgreSQL (asyncpg) и SQLite (aiosqlite) в зависимости от `DATABASE_URL`.
- Контекстный менеджер `get_session()` для использования в хэндлерах.

### FR-4: Redis FSM с graceful degradation
- При старте проверять доступность Redis через `PING`.
- Если Redis доступен: использовать `RedisStorage` (aiogram).
- Если Redis недоступен: fallback на `MemoryStorage` с логированием предупреждения.
- Логировать результат выбора хранилища при каждом запуске.

### FR-5: Shadow DB / Sandbox mode
- `DynamicSessionMaker`: класс, использующий `ContextVar[Optional[AsyncSession]]`.
- Метод `enable_sandbox(user_id)`: создаёт изолированный in-memory SQLite для конкретного пользователя и устанавливает `ContextVar`.
- Метод `disable_sandbox()`: сбрасывает `ContextVar` на `None` (используется боевая сессия).
- Метод `get_session()`: возвращает sandbox-сессию если установлена, иначе боевую.

### FR-6: Модели данных и миграции Alembic
- `app/db/models.py`: три модели SQLAlchemy 2.0:
  - `User` (таблица `users`): `telegram_id`, `username`, `timezone`, `delivery_time`, `is_active`, `created_at`.
  - `GoogleCredentials` (таблица `google_credentials`): `user_id` FK, `encrypted_refresh_token`, `token_uri`, `client_id`, `client_secret`, `scopes`, `spreadsheet_id`.
  - `TrackedTitle` (таблица `tracked_titles`): `id`, `user_id` FK, `shiki_id`, `title_name_ru`, `status_in_table`, `row_index`, `last_episodes_aired`, `total_episodes`, `updated_at`.
- `alembic.ini` + `migrations/`: настроить async Alembic окружение (`env.py`).
- Сгенерировать первую миграцию `init_tables`.

### FR-7: Шифрование OAuth токенов
- `app/core/security.py`: класс `TokenEncryptor` с методами `encrypt(token: str) -> str` и `decrypt(encrypted: str) -> str`.
- Использует `cryptography.fernet.Fernet` с ключом из `settings.ENCRYPTION_KEY`.
- Ошибки расшифровки логируются без повторного выброса (возвращает `None`).

### FR-8: Структурированное логирование
- `app/core/logger.py`: настройка `logging` с форматом `%(asctime)s [%(levelname)s] %(name)s: %(message)s`.
- Функция `setup_logging(level: str = "INFO")`.

## Non-Functional Requirements

- Python 3.11+, все async — через `asyncio`.
- Никаких секретов в коде — только из `.env` через `pydantic-settings`.
- Каждый публичный класс и функция — с docstring.
- Тесты покрывают 100% бизнес-логики (security, sandbox mode, session factory).

## Acceptance Criteria

- [ ] `docker-compose up -d` поднимает Redis без ошибок.
- [ ] `python -m app.main` стартует без ошибок (даже без реального Bot Token при mock).
- [ ] `alembic upgrade head` создаёт все три таблицы в БД.
- [ ] `pytest tests/ -v` — все тесты проходят.
- [ ] `pytest tests/ --cov=app/core --cov=app/db --cov-fail-under=80` — покрытие ≥ 80%.

## Out of Scope

- Telegram handlers и диалоги (Этап 5).
- Shikimori API клиент (Этап 2).
- Google Sheets клиент (Этап 3).
- APScheduler задачи (Этап 6).
