"""
Тесты для логики выбора FSM Storage (Redis vs MemoryStorage).

Стратегия: TDD Red Phase.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from aiogram.fsm.storage.memory import MemoryStorage


class TestCreateStorage:
    """Тесты функции create_storage()."""

    @pytest.mark.asyncio
    async def test_returns_memory_storage_when_redis_url_is_none(self) -> None:
        """Если redis_url=None, должен вернуться MemoryStorage."""
        from app.bot.storage import create_storage

        storage = await create_storage(redis_url=None)
        assert isinstance(storage, MemoryStorage)

    @pytest.mark.asyncio
    async def test_returns_memory_storage_when_redis_unavailable(self) -> None:
        """Если Redis недоступен (PING fail), должен вернуться MemoryStorage."""
        from app.bot.storage import create_storage

        with patch("app.bot.storage.redis.from_url") as mock_from_url:
            mock_client = AsyncMock()
            mock_client.ping.side_effect = ConnectionError("Redis unavailable")
            mock_from_url.return_value = mock_client

            storage = await create_storage(redis_url="redis://localhost:6379/0")
            assert isinstance(storage, MemoryStorage)

    @pytest.mark.asyncio
    async def test_logs_warning_when_redis_unavailable(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """При падении Redis в лог должно попадать предупреждение."""
        import logging

        from app.bot.storage import create_storage

        with patch("app.bot.storage.redis.from_url") as mock_from_url:
            mock_client = AsyncMock()
            mock_client.ping.side_effect = ConnectionError("Redis unavailable")
            mock_from_url.return_value = mock_client

            with caplog.at_level(logging.WARNING, logger="app.bot.storage"):
                await create_storage(redis_url="redis://localhost:6379/0")

            assert any(
                "redis" in record.message.lower() or "memor" in record.message.lower()
                for record in caplog.records
            )

    @pytest.mark.asyncio
    async def test_returns_redis_storage_when_available(self) -> None:
        """Если Redis доступен (PING OK), должен вернуться RedisStorage."""
        from aiogram.fsm.storage.redis import RedisStorage

        from app.bot.storage import create_storage

        with patch("app.bot.storage.redis.from_url") as mock_from_url:
            mock_client = AsyncMock()
            mock_client.ping.return_value = True
            mock_from_url.return_value = mock_client

            storage = await create_storage(redis_url="redis://localhost:6379/0")
            assert isinstance(storage, RedisStorage)
