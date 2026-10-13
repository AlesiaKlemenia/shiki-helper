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
        """Sandbox включается для sandbox-пользователя и отключается после хэндлера."""
        session_maker = DynamicSessionMaker(database_url="sqlite+aiosqlite:///:memory:")
        middleware = SandboxMiddleware(session_maker=session_maker, sandbox_user_ids={9999})

        # Событие с from_user во вложенном message (как Update в aiogram 3)
        from_user_mock = MagicMock()
        from_user_mock.id = 9999
        inner_message = MagicMock()
        inner_message.from_user = from_user_mock

        event = MagicMock(spec=TelegramObject)
        event.message = inner_message
        event.callback_query = None

        async def fake_handler(ev: TelegramObject, d: dict) -> str:
            assert session_maker.is_sandbox_active is True
            return "ok"

        await middleware(fake_handler, event, {})
        # После хэндлера sandbox отключен
        assert session_maker.is_sandbox_active is False

    @pytest.mark.asyncio
    async def test_sandbox_session_replaces_data_session(self) -> None:
        """Для sandbox-пользователя data['session'] должна быть подменена sandbox-сессией."""
        from sqlalchemy.ext.asyncio import AsyncSession

        session_maker = DynamicSessionMaker(database_url="sqlite+aiosqlite:///:memory:")
        middleware = SandboxMiddleware(session_maker=session_maker, sandbox_user_ids={9999})

        from_user_mock = MagicMock()
        from_user_mock.id = 9999
        inner_message = MagicMock()
        inner_message.from_user = from_user_mock

        event = MagicMock(spec=TelegramObject)
        event.message = inner_message
        event.callback_query = None

        # Кладём "production" сессию в data заранее
        production_session_mock = MagicMock(spec=AsyncSession)
        data: dict = {"session": production_session_mock}

        captured_session = None

        async def capture_handler(ev: TelegramObject, d: dict) -> str:
            nonlocal captured_session
            captured_session = d.get("session")
            return "ok"

        await middleware(capture_handler, event, data)

        # Внутри хэндлера сессия должна быть реальной AsyncSession (sandbox), не production-mock
        assert isinstance(captured_session, AsyncSession)
        # После завершения data["session"] восстановлена
        assert data["session"] is production_session_mock

    @pytest.mark.asyncio
    async def test_non_sandbox_user_passes_through(self) -> None:
        """Для обычного пользователя sandbox не активируется."""
        session_maker = DynamicSessionMaker(database_url="sqlite+aiosqlite:///:memory:")
        middleware = SandboxMiddleware(session_maker=session_maker, sandbox_user_ids={9999})

        from_user_mock = MagicMock()
        from_user_mock.id = 1111  # не в sandbox_user_ids
        inner_message = MagicMock()
        inner_message.from_user = from_user_mock

        event = MagicMock(spec=TelegramObject)
        event.message = inner_message
        event.callback_query = None

        async def fake_handler(ev: TelegramObject, d: dict) -> str:
            assert session_maker.is_sandbox_active is False
            return "ok"

        result = await middleware(fake_handler, event, {})
        assert result == "ok"
        assert session_maker.is_sandbox_active is False
