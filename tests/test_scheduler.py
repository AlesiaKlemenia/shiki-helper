"""Unit-тесты для SchedulerService (APScheduler).

Стратегия: TDD Red Phase.
"""
import datetime

from unittest.mock import MagicMock

import pytest
from aiogram import Bot

from app.db.models import Base, User
from app.db.session import create_session_factory
from app.services.scheduler import SchedulerService


class TestSchedulerService:
    """Тестирование управления фоновыми задачами через APScheduler."""

    @pytest.fixture
    async def db_session_factory(self):
        factory = create_session_factory("sqlite+aiosqlite:///:memory:")
        async with factory() as session:
            engine = session.bind
            assert engine is not None
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            # Добавим двух тестовых пользователей с разным временем рассылки
            u1 = User(telegram_id=101, username="user_one", timezone="Europe/Moscow", delivery_time=datetime.time(19, 0))
            u2 = User(telegram_id=102, username="user_two", timezone="Asia/Almaty", delivery_time=datetime.time(12, 0))
            session.add_all([u1, u2])
            await session.commit()
        return factory

    @pytest.mark.asyncio
    async def test_scheduler_lifecycle_and_user_jobs(self, db_session_factory) -> None:
        mock_bot = MagicMock(spec=Bot)
        service = SchedulerService(
            bot=mock_bot,
            session_factory=db_session_factory,
            database_url="sqlite+aiosqlite:///./shiki.db",
            admin_id=999,
            encryption_key="dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ=",
        )

        try:
            await service.start()
            assert service.scheduler.running

            # Синхронизация задач для пользователей
            await service.sync_user_digest_jobs()

            jobs = service.scheduler.get_jobs()
            job_ids = [j.id for j in jobs]

            # Должны быть задачи для пользователей 101 и 102
            assert "digest_user_101" in job_ids
            assert "digest_user_102" in job_ids

            # Должна присутствовать задача ночного бэкапа (в 03:00 UTC)
            assert "daily_backup_job" in job_ids
        finally:
            await service.shutdown()
            assert not service.scheduler.running
