"""
Alembic environment configuration для async SQLAlchemy.

Использует asyncio режим через run_async_migrations() для совместимости
с asyncpg (PostgreSQL) и aiosqlite (SQLite).
"""
from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

# Добавляем корень проекта в sys.path для импорта пакета app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Импортируем Base и все модели для автогенерации миграций
from app.db.models import Base  # noqa: F401  # Загружает все модели

# ---------------------------------------------------------------------------
# Alembic Config
# ---------------------------------------------------------------------------
config = context.config

# Настройка логирования из alembic.ini
if config.config_file_name is not None:
    # disable_existing_loggers=False: иначе fileConfig глушит уже созданные
    # логгеры (aiogram, aiogram.dispatcher, __main__) и все ошибки диспетчера
    # становятся невидимыми в логах.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Метаданные для автогенерации миграций
target_metadata = Base.metadata


def get_database_url() -> str:
    """Получает DATABASE_URL из переменных окружения или app.config.

    Returns:
        Строка подключения к БД.

    Raises:
        ValueError: Если DATABASE_URL не задан.
    """
    # Сначала проверяем переменную окружения напрямую (для CI/миграций)
    url = os.environ.get("DATABASE_URL")
    if not url:
        try:
            from app.config import settings
            url = settings.database_url
        except Exception as exc:
            raise ValueError(
                "DATABASE_URL не задан. "
                "Установите переменную окружения DATABASE_URL или создайте .env файл."
            ) from exc

    from app.db.session import normalize_database_url
    url = normalize_database_url(url)
    return url


def run_migrations_offline() -> None:
    """Запуск миграций в 'offline' режиме (генерация SQL без подключения).

    Используется для генерации SQL-скриптов: alembic upgrade --sql
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Выполняет миграции с переданным синхронным подключением.

    Args:
        connection: Синхронное DBAPI подключение.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=True,  # Необходимо для SQLite ALTER TABLE
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Создаёт async engine и запускает миграции через синхронный wrapper.

    Используется asyncio.run() или event loop для выполнения.
    """
    url = get_database_url()

    # Формируем конфигурацию для async engine
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # NullPool для миграций — не нужен пул
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Запуск миграций в 'online' режиме через asyncio event loop."""
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Определяем режим запуска
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
