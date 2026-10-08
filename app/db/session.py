"""
Async подключение к базе данных через SQLAlchemy 2.0.

Поддерживает PostgreSQL (asyncpg) и SQLite (aiosqlite).
Определяет фабрику сессий и контекстный менеджер для использования
в middleware и сервисах бота.

Использование:
    from app.db.session import create_session_factory, create_async_engine_from_url
    from app.config import settings

    engine = create_async_engine_from_url(settings.database_url)
    session_factory = create_session_factory(settings.database_url)

    async with session_factory() as session:
        result = await session.execute(select(User))
"""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


logger = logging.getLogger(__name__)


def create_async_engine_from_url(database_url: str) -> AsyncEngine:
    """Создаёт async SQLAlchemy engine по строке подключения.

    Автоматически определяет диалект (PostgreSQL/SQLite) по схеме URL.
    Для PostgreSQL включает connection pooling, для SQLite — отключает
    (не поддерживается при многопоточном использовании).

    Args:
        database_url: Строка подключения к БД.
            PostgreSQL: 'postgresql+asyncpg://user:pass@host/db'
            SQLite: 'sqlite+aiosqlite:///./shiki.db' или 'sqlite+aiosqlite:///:memory:'

    Returns:
        Настроенный AsyncEngine.
    """
    is_sqlite = database_url.startswith("sqlite")

    engine_kwargs: dict = {
        "echo": False,  # Включить для отладки SQL: True
    }

    if not is_sqlite:
        # Для PostgreSQL c драйвером asyncpg параметр sslmode не поддерживается напрямую в DBAPI kwargs,
        # поэтому заменяем sslmode= на ssl=, если он передан в строке подключения.
        if "sslmode=" in database_url:
            database_url = database_url.replace("sslmode=require", "ssl=require").replace("sslmode=", "ssl=")
    else:
        # SQLite не поддерживает connection pool в async режиме
        engine_kwargs["connect_args"] = {"check_same_thread": False}

    try:
        engine = create_async_engine(database_url, **engine_kwargs)
        logger.info(
            "Async engine создан. Диалект: %s",
            engine.dialect.name,
        )
        return engine
    except Exception as exc:
        logger.error("Ошибка создания async engine: %s", exc)
        raise


def create_session_factory(
    database_url: str,
) -> async_sessionmaker[AsyncSession]:
    """Создаёт фабрику async сессий SQLAlchemy.

    Возвращаемая фабрика используется как контекстный менеджер:
        async with session_factory() as session:
            ...

    Args:
        database_url: Строка подключения к БД.

    Returns:
        async_sessionmaker, настроенный с autocommit=False, autoflush=False
        и expire_on_commit=False (важно для async использования).
    """
    engine = create_async_engine_from_url(database_url)
    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    return factory
