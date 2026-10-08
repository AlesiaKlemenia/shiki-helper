"""Middleware поддержки режима изоляции Sandbox (Shadow DB)."""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional, Set

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.db.sandbox import DynamicSessionMaker


class SandboxMiddleware(BaseMiddleware):
    """Активирует in-memory изолированную базу для выбранных пользователей (например, тестеров/админа)."""

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
        from_user = getattr(event, "from_user", None)
        user_id = getattr(from_user, "id", None) if from_user else None

        should_sandbox = isinstance(user_id, int) and user_id in self.sandbox_user_ids
 
        if should_sandbox and isinstance(user_id, int):
            await self.session_maker.enable_sandbox(user_id=user_id)
            try:
                return await handler(event, data)
            finally:
                await self.session_maker.disable_sandbox()

        return await handler(event, data)
