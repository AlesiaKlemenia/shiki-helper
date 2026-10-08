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

    # --- 4. Запуск polling ---
    try:
        logger.info("Бот запущен. Начинаем polling...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as exc:
        logger.error("Критическая ошибка polling: %s", exc)
        raise
    finally:
        await bot.session.close()
        if hasattr(storage, "close"):
            await storage.close()
        logger.info("Бот остановлен. Все соединения закрыты.")


if __name__ == "__main__":
    asyncio.run(main())
