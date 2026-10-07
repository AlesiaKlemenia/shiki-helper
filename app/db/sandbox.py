"""
Shadow DB / Sandbox mode для безопасного тестирования UI и admin-операций.

DynamicSessionMaker позволяет переключать сессию конкретного пользователя
на изолированную in-memory SQLite базу данных, не затрагивая боевые данные.

Механизм основан на ContextVar — каждый asyncio Task (запрос пользователя)
имеет свой контекст, поэтому переключение sandbox одного пользователя
не влияет на других.

Использование:
    from app.db.sandbox import DynamicSessionMaker
    from app.config import settings

    # Инициализация (один раз при старте)
    session_maker = DynamicSessionMaker(database_url=settings.database_url)

    # Включение sandbox для пользователя
    await session_maker.enable_sandbox(user_id=12345)

    # Получение сессии (автоматически возвращает sandbox)
    async with session_maker.get_session() as session:
        ...

    # Отключение sandbox
    await session_maker.disable_sandbox()
"""
from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


logger = logging.getLogger(__name__)

# ContextVar хранит sandbox engine для текущего asyncio Task.
# Каждый запрос пользователя выполняется в своём Task — изоляция гарантирована.
_sandbox_engine_var: ContextVar[Optional[AsyncEngine]] = ContextVar(
    "_sandbox_engine_var", default=None
)


class DynamicSessionMaker:
    """Фабрика сессий с поддержкой Shadow DB / Sandbox mode.

    Хранит боевую фабрику сессий и умеет переключать на in-memory SQLite
    через ContextVar для изолированного тестирования.

    Args:
        database_url: Строка подключения к боевой БД.
    """

    def __init__(self, database_url: str) -> None:
        """Инициализирует фабрику с подключением к боевой БД.

        Args:
            database_url: Строка подключения к боевой БД.
        """
        self._database_url = database_url
        self._production_engine = create_async_engine(
            database_url,
            connect_args={"check_same_thread": False}
            if database_url.startswith("sqlite")
            else {},
        )
        self._production_factory = async_sessionmaker(
            bind=self._production_engine,
            class_=AsyncSession,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )

    @property
    def is_sandbox_active(self) -> bool:
        """Возвращает True если sandbox включён в текущем контексте.

        Returns:
            True если ContextVar содержит sandbox engine.
        """
        return _sandbox_engine_var.get() is not None

    async def enable_sandbox(self, user_id: int) -> None:
        """Включает sandbox mode для текущего asyncio Task (пользователя).

        Создаёт новый изолированный in-memory SQLite engine и устанавливает
        его в ContextVar текущего Task.

        Args:
            user_id: Telegram ID пользователя (используется для логирования).
        """
        sandbox_engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        _sandbox_engine_var.set(sandbox_engine)
        logger.info(
            "Sandbox mode включён для пользователя user_id=%d. "
            "Используется in-memory SQLite (боевые данные не затрагиваются).",
            user_id,
        )

    async def disable_sandbox(self) -> None:
        """Отключает sandbox mode и возвращает к боевой сессии.

        Также закрывает изолированный sandbox engine для освобождения ресурсов.
        """
        sandbox_engine = _sandbox_engine_var.get()
        if sandbox_engine is not None:
            await sandbox_engine.dispose()
            _sandbox_engine_var.set(None)
            logger.info("Sandbox mode отключён. Переключение на боевую БД.")

    def get_session(self) -> async_sessionmaker[AsyncSession]:
        """Возвращает фабрику сессий: sandbox если активен, иначе боевую.

        Returns:
            async_sessionmaker для текущего контекста (sandbox или production).
        """
        sandbox_engine = _sandbox_engine_var.get()

        if sandbox_engine is not None:
            # Создаём фабрику поверх sandbox engine
            return async_sessionmaker(
                bind=sandbox_engine,
                class_=AsyncSession,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False,
            )

        return self._production_factory

    async def dispose(self) -> None:
        """Закрывает все соединения боевого engine при shutdown."""
        await self._production_engine.dispose()
        logger.info("DynamicSessionMaker: боевой engine закрыт.")
