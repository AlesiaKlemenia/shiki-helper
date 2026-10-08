"""Unit-тесты для BackupService (резервное копирование БД в Telegram).

Стратегия: TDD Red Phase.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram import Bot

from app.db.models import Base, User
from app.db.session import create_session_factory
from app.services.backup import BackupService


class TestBackupService:
    """Тестирование создания и отправки резервной копии БД."""

    @pytest.fixture
    async def sqlite_db_path(self, tmp_path: pytest.TempPathFactory) -> str:
        db_file = tmp_path / "test_backup.db" # type: ignore[operator]
        url = f"sqlite+aiosqlite:///{db_file}"
        factory = create_session_factory(url)
        async with factory() as session:
            engine = session.bind
            assert engine is not None
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            user = User(telegram_id=111, username="test_backup_user")
            session.add(user)
            await session.commit()
        return str(db_file)

    @pytest.mark.asyncio
    async def test_create_sqlite_backup_bytes(self, sqlite_db_path: str) -> None:
        service = BackupService(database_url=f"sqlite+aiosqlite:///{sqlite_db_path}")
        backup_bytes = await service.create_backup_bytes()

        assert isinstance(backup_bytes, bytes)
        assert len(backup_bytes) > 0
        # Проверяем сигнатуру заголовка SQLite
        assert backup_bytes.startswith(b"SQLite format 3")

    @pytest.mark.asyncio
    async def test_send_backup_to_telegram(self, sqlite_db_path: str) -> None:
        service = BackupService(database_url=f"sqlite+aiosqlite:///{sqlite_db_path}")
        mock_bot = MagicMock(spec=Bot)
        mock_bot.send_document = AsyncMock()

        await service.send_backup(bot=mock_bot, admin_id=999999)

        assert mock_bot.send_document.called
        call_kwargs = mock_bot.send_document.call_args.kwargs
        assert call_kwargs["chat_id"] == 999999
        assert "caption" in call_kwargs
        assert "Резервная копия" in call_kwargs["caption"]
        document = call_kwargs["document"]
        assert hasattr(document, "read") or hasattr(document, "filename")
