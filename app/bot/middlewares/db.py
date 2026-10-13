"""Middleware внедрения асинхронной сессии SQLAlchemy в контекст хэндлеров aiogram."""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)


class DbSessionMiddleware(BaseMiddleware):
    """Предоставляет сессию БД для каждого входящего апдейта."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        super().__init__()
        self.session_factory = session_factory

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Диагностическое логирование: каждый входящий апдейт
        if isinstance(event, Update):
            update_type = "unknown"
            user_id = None
            if event.message:
                update_type = "message"
                user_id = event.message.from_user.id if event.message.from_user else None
            elif event.callback_query:
                update_type = "callback_query"
                user_id = event.callback_query.from_user.id if event.callback_query.from_user else None
            logger.info(
                "[DB MW] Получен апдейт: type=%s, update_id=%s, user_id=%s",
                update_type,
                event.update_id,
                user_id,
            )

        async with self.session_factory() as session:
            data["session"] = session
            return await handler(event, data)

