"""Middleware поддержки режима изоляции Sandbox (Shadow DB)."""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict, Optional, Set

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Base
from app.db.sandbox import DynamicSessionMaker

logger = logging.getLogger(__name__)


class SandboxMiddleware(BaseMiddleware):
    """Активирует in-memory изолированную базу для выбранных пользователей (например, тестеров/админа).

    Подменяет data["session"] изолированной SQLite-сессией вместо production,
    чтобы sandbox-пользователи не затрагивали боевые данные.
    """

    def __init__(
        self,
        session_maker: DynamicSessionMaker,
        sandbox_user_ids: Optional[Set[int]] = None,
    ) -> None:
        super().__init__()
        self.session_maker = session_maker
        self.sandbox_user_ids = sandbox_user_ids or set()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Update-объект не имеет from_user, ищем вложенный message/callback_query
        inner_event = (
            getattr(event, "message", None)
            or getattr(event, "callback_query", None)
            or event
        )
        from_user = getattr(inner_event, "from_user", None)
        user_id = getattr(from_user, "id", None) if from_user else None

        should_sandbox = isinstance(user_id, int) and user_id in self.sandbox_user_ids

        if should_sandbox and isinstance(user_id, int):
            try:
                await self.session_maker.enable_sandbox(user_id=user_id)

                # Инициализируем схему в in-memory SQLite (create_all)
                sandbox_engine = self.session_maker._sandbox_engine_var_get()
                if sandbox_engine is not None:
                    try:
                        async with sandbox_engine.begin() as conn:
                            await conn.run_sync(Base.metadata.create_all)
                    except Exception as schema_exc:
                        logger.error(
                            "Не удалось создать схему в sandbox для user_id=%d: %s",
                            user_id,
                            schema_exc,
                        )

                # Подменяем сессию в data на sandbox-сессию
                sandbox_session: Optional[AsyncSession] = None
                try:
                    async with self.session_maker.get_session() as session:
                        sandbox_session = session
                        old_session: Optional[AsyncSession] = data.get("session")
                        data["session"] = sandbox_session
                        try:
                            return await handler(event, data)
                        finally:
                            data["session"] = old_session
                except Exception as exc:
                    logger.error(
                        "Ошибка в sandbox-сессии для user_id=%d: %s", user_id, exc
                    )
                    raise
            finally:
                await self.session_maker.disable_sandbox()

        return await handler(event, data)

