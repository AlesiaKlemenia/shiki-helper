"""
Точка входа Shiki-Helper: запуск Telegram-бота.

Инициализирует:
    - Логирование (setup_logging)
    - Async engine и session factory (SQLAlchemy)
    - FSM Storage (Redis с graceful degradation на MemoryStorage)
    - Dispatcher + Bot (aiogram 3.x)
    - Polling

Использование:
    python -m app.main
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher


logger = logging.getLogger(__name__)


async def main() -> None:
    """Главная async функция запуска бота.

    Raises:
        SystemExit: При критической ошибке конфигурации.
    """
    # --- 1. Логирование ---
    from app.core.logger import setup_logging

    try:
        from app.config import settings
        setup_logging(settings.log_level)
    except Exception as exc:
        # Логирование ещё не настроено — используем базовый print
        import sys
        print(f"[CRITICAL] Ошибка загрузки конфигурации: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    logger.info("Запуск Shiki-Helper бота...")

    # --- 1.1 Автоматическая инициализация схемы БД (Alembic upgrade head / create_all) ---
    try:
        from alembic.config import Config
        from alembic import command
        alembic_cfg = Config("alembic.ini")
        await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
        logger.info("Миграции базы данных успешно применены.")
    except Exception as exc:
        logger.warning("Alembic upgrade head завершился с предупреждением: %s. Применяем fallback Base.metadata.create_all...", exc)
        try:
            from app.db.models import Base
            from app.db.session import create_async_engine_from_url
            init_engine = create_async_engine_from_url(settings.database_url)
            async with init_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            await init_engine.dispose()
            logger.info("Схема базы данных успешно создана через Base.metadata.create_all.")
        except Exception as create_exc:
            logger.error("Критическая ошибка инициализации таблиц базы данных: %s", create_exc)
            raise

    # --- 2. FSM Storage (Redis / MemoryStorage) ---
    from app.bot.storage import create_storage

    try:
        storage = await create_storage(redis_url=settings.redis_url)
    except Exception as exc:
        logger.error("Ошибка инициализации FSM storage: %s", exc)
        raise

    # --- 3. Инициализация Bot и Dispatcher ---
    from aiogram_dialog import setup_dialogs
    from app.bot.dialogs.onboarding.dialog import onboarding_dialog
    from app.bot.dialogs.titles.dialog import titles_dialog
    from app.bot.handlers.common import common_router
    from app.bot.handlers.manual import manual_router
    from app.bot.middlewares.db import DbSessionMiddleware
    from app.bot.middlewares.sandbox import SandboxMiddleware
    from app.db.sandbox import DynamicSessionMaker
    from app.db.session import create_session_factory

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=storage)

    dynamic_session_maker = DynamicSessionMaker(database_url=settings.database_url)
    session_factory = create_session_factory(database_url=settings.database_url)

    # Регистрация Middlewares
    dp.update.middleware(DbSessionMiddleware(session_factory=session_factory))
    dp.update.middleware(
        SandboxMiddleware(
            session_maker=dynamic_session_maker,
            sandbox_user_ids=set(settings.sandbox_user_ids),
        )
    )

    # Регистрация диалогов aiogram-dialog
    dp.include_router(onboarding_dialog)
    dp.include_router(titles_dialog)

    # Регистрация основных роутеров
    dp.include_router(common_router)
    dp.include_router(manual_router)

    # Настройка aiogram-dialog
    setup_dialogs(dp)

    # --- 4. Сервер Healthcheck (aiohttp.web для Render $PORT) ---
    from app.services.health import HealthcheckServer

    me = await bot.get_me()
    health_server = HealthcheckServer(
        port=settings.port,
        bot_username=me.username or "shiki_helper_bot",
    )
    await health_server.start()

    # --- 5. Планировщик APScheduler ---
    from app.services.scheduler import SchedulerService

    scheduler = SchedulerService(
        bot=bot,
        session_factory=session_factory,
        database_url=settings.database_url,
        admin_id=settings.admin_telegram_id,
        encryption_key=settings.encryption_key,
    )
    await scheduler.start()
    await scheduler.sync_user_digest_jobs()

    # Уведомление администратора о старте сервиса
    try:
        await bot.send_message(
            chat_id=settings.admin_telegram_id,
            text=f"🟢 <b>Shiki-Helper успешно запущен!</b>\n"
                 f"🤖 Бот: @{me.username}\n"
                 f"🌐 Healthcheck: <code>:{settings.port}/health</code>\n"
                 f"⏰ Планировщик активен.",
            parse_mode="HTML",
        )
    except Exception as exc:
        logger.warning("Не удалось отправить стартовое уведомление админу: %s", exc)

    # --- 6. Запуск polling ---
    try:
        logger.info("Бот запущен. Начинаем polling...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as exc:
        logger.error("Критическая ошибка polling: %s", exc)
        raise
    finally:
        await scheduler.shutdown()
        await health_server.stop()
        await dynamic_session_maker.dispose()
        await bot.session.close()
        if hasattr(storage, "close"):
            await storage.close()
        logger.info("Бот остановлен. Все соединения закрыты.")


if __name__ == "__main__":
    asyncio.run(main())
