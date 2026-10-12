"""Глобальные обработчики ошибок бота."""
from __future__ import annotations

import logging
from typing import Any

from aiogram import Router
from aiogram.filters import ExceptionTypeFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import ErrorEvent, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram_dialog.api.exceptions import UnknownIntent

from app.bot.keyboards import get_persistent_main_keyboard

logger = logging.getLogger(__name__)

errors_router = Router(name="errors_router")


def get_main_menu_inline_keyboard() -> InlineKeyboardMarkup:
    """Возвращает Inline-клавиатуру главного меню."""
    return InlineKeyboardMarkup(
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


@errors_router.error(ExceptionTypeFilter(UnknownIntent))
async def handle_unknown_intent(event: ErrorEvent, state: FSMContext) -> None:
    """Обработка устаревших колбэков aiogram-dialog (UnknownIntent).

    При перезапуске бота или устаревании стэка диалога молча сбрасывает FSM
    и отправляет пользователю свежее главное меню без ошибок и падений.
    """
    logger.warning("Перехвачено исключение UnknownIntent для события: %s", event.exception)

    try:
        await state.clear()
    except Exception as exc:
        logger.error("Ошибка при сбросе FSM состояния: %s", exc)

    text = (
        "🎛 *Главное меню Shiki\\-Helper*\n\n"
        "Сессия предыдущего диалога завершена\\. Выберите интересующий раздел:"
    )

    if event.update.callback_query:
        cb = event.update.callback_query
        try:
            await cb.answer()
        except Exception as exc:
            logger.debug("Не удалось ответить на устаревший callback query: %s", exc)

        target_message = cb.message
        if isinstance(target_message, Message):
            try:
                await target_message.answer(
                    text,
                    reply_markup=get_main_menu_inline_keyboard(),
                    parse_mode="MarkdownV2",
                )
            except Exception as exc:
                logger.error("Ошибка отправки меню при UnknownIntent: %s", exc)
    elif event.update.message:
        try:
            await event.update.message.answer(
                text,
                reply_markup=get_main_menu_inline_keyboard(),
                parse_mode="MarkdownV2",
            )
        except Exception as exc:
            logger.error("Ошибка отправки меню при UnknownIntent: %s", exc)
