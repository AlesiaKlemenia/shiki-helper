"""Сервис планировщика задач на базе AsyncIOScheduler (APScheduler)."""
from __future__ import annotations

import logging
import asyncio

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import User
from app.services.backup import BackupService
from app.services.digest import format_digest_html
from app.services.tracker import TrackerService

logger = logging.getLogger(__name__)


class SchedulerService:
    """Управляет жизненным циклом планировщика задач и динамической регистрацией джоб."""

    def __init__(
        self,
        bot: Bot,
        session_factory: async_sessionmaker[AsyncSession],
        database_url: str,
        admin_id: int,
        encryption_key: str,
    ) -> None:
        self.bot = bot
        self.session_factory = session_factory
        self.database_url = database_url
        self.admin_id = admin_id
        self.encryption_key = encryption_key

        self.scheduler = AsyncIOScheduler(
            job_defaults={
                "misfire_grace_time": 300,  # 5 минут допустимого опоздания задачи
                "coalesce": True,            # Объединять пропущенные запуски
            }
        )
        self.backup_service = BackupService(database_url=self.database_url)

    async def start(self) -> None:
        """Запускает планировщик и регистрирует системные задачи."""
        if not self.scheduler.running:
            self._register_system_jobs()
            self.scheduler.start()
            logger.info("AsyncIOScheduler успешно запущен.")

    async def shutdown(self) -> None:
        """Корректно останавливает планировщик."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            await asyncio.sleep(0.02)
            logger.info("AsyncIOScheduler остановлен.")

    def _register_system_jobs(self) -> None:
        """Регистрирует периодические системные задачи (бэкап базы данных)."""
        # Ежедневный бэкап в 03:00 UTC
        self.scheduler.add_job(
            func=self._run_backup_job,
            trigger=CronTrigger(hour=3, minute=0, timezone="UTC"),
            id="daily_backup_job",
            replace_existing=True,
        )

    async def _run_backup_job(self) -> None:
        """Исполняемая задача бэкапа базы данных."""
        try:
            await self.backup_service.send_backup(bot=self.bot, admin_id=self.admin_id)
        except Exception as exc:
            logger.error("Ошибка при выполнении планового бэкапа: %s", exc)

    async def sync_user_digest_jobs(self) -> None:
        """Динамически регистрирует или обновляет задачи рассылки дайджеста для пользователей."""
        async with self.session_factory() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()

        for user in users:
            self.register_user_digest_job(user)

    def register_user_digest_job(self, user: User) -> None:
        """Регистрирует индивидуальную cron-задачу рассылки для пользователя."""
        job_id = f"digest_user_{user.telegram_id}"
        delivery_time = user.delivery_time
        user_tz = user.timezone or "Europe/Moscow"

        if delivery_time is not None and hasattr(delivery_time, "hour") and hasattr(delivery_time, "minute"):
            hour = int(delivery_time.hour)
            minute = int(delivery_time.minute)
        elif isinstance(delivery_time, str):
            try:
                hour_str, minute_str = delivery_time.split(":")
                hour = int(hour_str)
                minute = int(minute_str)
            except ValueError:
                hour, minute = 19, 0
        else:
            hour, minute = 19, 0

        self.scheduler.add_job(
            func=self._run_user_digest,
            trigger=CronTrigger(hour=hour, minute=minute, timezone=user_tz),
            args=[user.telegram_id],
            id=job_id,
            replace_existing=True,
        )
        logger.debug("Зарегистрирована рассылка для user_id=%d в %02d:%02d (%s)", user.telegram_id, hour, minute, user_tz)

    async def _run_user_digest(self, user_id: int) -> None:
        """Выполняет проверку обновлений и отправляет дайджест пользователю."""
        logger.info("Запуск планового дайджеста для пользователя user_id=%d", user_id)
        async with self.session_factory() as session:
            tracker = TrackerService(
                session=session,
                encryption_key=self.encryption_key,
            )
            try:
                result = await tracker.check_user_updates_full(user_id=user_id)
                if result.has_content:
                    text = format_digest_html(result.deltas, result.debts)
                    await self.bot.send_message(
                        chat_id=user_id,
                        text=text,
                        parse_mode="MarkdownV2",
                        disable_web_page_preview=True,
                    )
                else:
                    logger.info("Новых серий и долгов для user_id=%d нет, дайджест не отправляется.", user_id)
            except Exception as exc:
                logger.error("Ошибка при формировании планового дайджеста для user_id=%d: %s", user_id, exc)
