"""Unit-тесты для middleware сессий БД и Sandbox."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import TelegramObject

from app.bot.middlewares.db import DbSessionMiddleware
from app.bot.middlewares.sandbox import SandboxMiddleware
from app.db.sandbox import DynamicSessionMaker
from app.db.session import create_session_factory


class TestDbSessionMiddleware:
    """Тестирование внедрения сессии БД в aiogram."""

    @pytest.mark.asyncio
    async def test_injects_session_and_closes_it(self) -> None:
        factory = create_session_factory("sqlite+aiosqlite:///:memory:")
        middleware = DbSessionMiddleware(session_factory=factory)

        handler = AsyncMock(return_value="handler_result")
        event = MagicMock(spec=TelegramObject)
        data: dict = {}

        result = await middleware(handler, event, data)

        assert result == "handler_result"
        assert "session" in data
        session = data["session"]
        # После завершения middleware сессия закрыта
        assert not session.is_active or session.sync_session._transaction is None


class TestSandboxMiddleware:
    """Тестирование переключения в sandbox mode."""

    @pytest.mark.asyncio
    async def test_enables_and_disables_sandbox_for_sandbox_user(self) -> None:
        session_maker = DynamicSessionMaker(database_url="sqlite+aiosqlite:///:memory:")
        middleware = SandboxMiddleware(session_maker=session_maker, sandbox_user_ids={9999})

        event = MagicMock()
        event.from_user.id = 9999

        async def fake_handler(ev: TelegramObject, d: dict) -> str:
            assert session_maker.is_sandbox_active is True
            return "ok"

        await middleware(fake_handler, event, {})
        # После хэндлера sandbox отключен
        assert session_maker.is_sandbox_active is False
