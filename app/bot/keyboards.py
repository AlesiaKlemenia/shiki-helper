"""Клавиатуры бота Shiki-Helper."""
from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def get_persistent_main_keyboard() -> ReplyKeyboardMarkup:
    """Возвращает постоянную нижнюю Reply-клавиатуру навигации.

    Клавиатура зафиксирована внизу экрана (is_persistent=True) и адаптирует
    размер под экран смартфона (resize_keyboard=True).
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🏠 Главное меню"),
                KeyboardButton(text="📋 Мой список"),
                KeyboardButton(text="⚙️ Настройки"),
            ]
        ],
        resize_keyboard=True,
        is_persistent=True,
    )
