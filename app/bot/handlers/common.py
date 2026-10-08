"""Базовые команды бота: /start, /help, /menu."""
from __future__ import annotations

import logging
from typing import Any
from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User

logger = logging.getLogger(__name__)
common_router = Router(name="common_router")


@common_router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    """Обработчик команды /start."""
    if not message.from_user:
        return

    user_id = message.from_user.id
    username = message.from_user.username

    user = await session.get(User, user_id)
    if user is None:
        user = User(
            telegram_id=user_id,
            username=username,
            timezone="Europe/Moscow",
        )
        session.add(user)
        await session.commit()
        logger.info("Зарегистрирован новый пользователь %d (@%s)", user_id, username)

    text = (
        f"👋 <b>Добро пожаловать в Shiki-Helper, {message.from_user.first_name}!</b>\n\n"
        "Я помогаю отслеживать выход новых серий аниме на Shikimori и синхронизирую "
        "статусы с вашими Google Таблицами рабочих релизов.\n\n"
        "Команды:\n"
        "• <b>/menu</b> — главное интерактивное меню\n"
        "• <b>/sync</b> — проверить обновления серий прямо сейчас\n"
        "• <b>/help</b> — подробная справка по боту"
    )
    await message.answer(text, parse_mode="HTML")


@common_router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Обработчик команды /help."""
    text = (
        "📖 <b>Справка по командам Shiki-Helper:</b>\n\n"
        "• <b>/start</b> — запустить бота и обновить профиль\n"
        "• <b>/menu</b> — главное интерактивное меню управления\n"
        "• <b>/sync</b> — запустить немедленную сверку серий и получить дайджест\n"
        "• <b>/help</b> — показать эту справку\n\n"
        "<i>Следите за новыми сериями без ручной рутины! 🚀</i>"
    )
    await message.answer(text, parse_mode="HTML")


@common_router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    """Обработчик команды /menu — главное меню бота."""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Мои тайтлы", callback_data="menu_open_titles"),
            ],
            [
                InlineKeyboardButton(text="⚙️ Настройки (Онбординг)", callback_data="menu_open_settings"),
                InlineKeyboardButton(text="🔄 Синхронизация", callback_data="menu_trigger_sync"),
            ],
        ]
    )

    text = (
        "🎛 <b>Главное меню Shiki-Helper</b>\n\n"
        "Выберите интересующий раздел управления:"
    )
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


@common_router.callback_query(lambda c: c.data == "menu_open_titles")
async def cb_open_titles(query: Any, dialog_manager: Any) -> None:
    """Открытие диалога тайтлов из меню."""
    from app.bot.dialogs.titles.dialog import TitlesSG
    from aiogram_dialog import StartMode

    await query.answer()
    await dialog_manager.start(TitlesSG.list_titles, mode=StartMode.RESET_STACK)


@common_router.callback_query(lambda c: c.data == "menu_open_settings")
async def cb_open_settings(query: Any, dialog_manager: Any) -> None:
    """Открытие диалога онбординга/настроек из меню."""
    from app.bot.dialogs.onboarding.dialog import OnboardingSG
    from aiogram_dialog import StartMode

    await query.answer()
    await dialog_manager.start(OnboardingSG.timezone, mode=StartMode.RESET_STACK)


@common_router.callback_query(lambda c: c.data == "menu_trigger_sync")
async def cb_trigger_sync(query: Any, session: AsyncSession) -> None:
    """Запуск немедленной синхронизации по кнопке из меню."""
    from app.config import settings
    from app.services.digest import format_digest_html
    from app.services.tracker import TrackerService

    await query.answer("Запускаем синхронизацию...")
    user_id = query.from_user.id

    if query.message:
        await query.message.answer("🔍 <i>Сверяем обновления серий с Shikimori и Google Таблицей...</i>", parse_mode="HTML")

    tracker = TrackerService(
        session=session,
        encryption_key=settings.encryption_key,
    )

    try:
        deltas = await tracker.check_user_updates(user_id=user_id)
        digest_text = format_digest_html(deltas)
        if query.message:
            await query.message.answer(digest_text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as exc:
        logger.error("Ошибка при выполнении синхронизации из меню для пользователя %d: %s", user_id, exc)
        if query.message:
            await query.message.answer(
                f"⚠️ <b>Произошла ошибка при сверке обновлений:</b>\n<code>{exc}</code>",
                parse_mode="HTML",
            )

