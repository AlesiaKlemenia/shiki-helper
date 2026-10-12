"""Диалог онбординга (Onboarding Dialog) на aiogram-dialog.

Шаги:
1. Выбор времени ежедневного дайджеста (по МСК, ввод в формате ЧЧ:ММ с regex-валидацией).
2. Подключение Google Таблицы со ссылкой на официальный шаблон (или пропуск).
"""
from __future__ import annotations

import datetime
import re
from typing import Any

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.kbd import Button
from aiogram_dialog.widgets.text import Const, Format
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.utils import escape_md_v2, escape_md_v2_url
from app.db.models import User

TIME_REGEX = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
SHEETS_TEMPLATE_URL = "https://docs.google.com/spreadsheets/d/1wiDiRPt_zliosdTpC9R-1tREAy1x5h_OnDBQN_sb3Lc/edit?usp=sharing"


class OnboardingSG(StatesGroup):
    """Состояния мастера настройки онбординга."""

    timezone = State()  # Сохранено как начальное состояние для совместимости (перенаправляет на delivery_time)
    delivery_time = State()
    google_setup = State()


def validate_time_format(text: str) -> str:
    """Проверяет строку времени на соответствие формату ЧЧ:ММ (00:00 - 23:59)."""
    clean_text = text.strip()
    if not TIME_REGEX.match(clean_text):
        raise ValueError("Неверный формат времени. Используйте ЧЧ:ММ (например, 19:30 или 09:00)")
    return clean_text


async def on_time_input_success(
    event: Message,
    widget: Any,
    manager: DialogManager,
    time_str: str,
) -> None:
    """Обработчик успешного ввода времени в онбординге."""
    middleware_data = manager.middleware_data
    session: AsyncSession = middleware_data["session"]
    user_id = event.from_user.id if event.from_user else 0

    hours, minutes = map(int, time_str.split(":"))
    delivery_time_obj = datetime.time(hours, minutes, 0)

    user = await session.get(User, user_id)
    if user:
        user.delivery_time = delivery_time_obj
        user.timezone = "Europe/Moscow"
        await session.commit()

    manager.dialog_data["delivery_time"] = time_str
    await manager.switch_to(OnboardingSG.google_setup)


async def on_time_input_error(
    event: Message,
    widget: Any,
    manager: DialogManager,
    error: ValueError,
) -> None:
    """Обработчик некорректного формата времени в онбординге."""
    await event.answer(
        "⚠️ *Некорректный формат времени\\!*\n\n"
        "Пожалуйста, введите время в формате *ЧЧ:ММ* \\(по московскому времени, 00:00 — 23:59\\)\\.\n"
        "Примеры: `19:00`, `09:30`, `22:15`\\.",
        parse_mode="MarkdownV2",
    )


async def on_skip_google(
    event: Any,
    button: Button,
    manager: DialogManager,
) -> None:
    """Завершение онбординга (пропуск или ознакомление с таблицей)."""
    await manager.done()


async def get_onboarding_google_data(**kwargs: Any) -> dict[str, str]:
    """Геттер ссылки на эталонный шаблон таблицы."""
    return {
        "template_url": escape_md_v2_url(SHEETS_TEMPLATE_URL),
    }


onboarding_dialog = Dialog(
    # Окно-алиас начального состояния (сразу переходит к вводу времени по МСК)
    Window(
        Const("⏳ Инициализация мастера настройки..."),
        state=OnboardingSG.timezone,
        getter=lambda **kw: {},
    ),
    # Окно 1: Время рассылки по МСК
    Window(
        Const(
            "⏰ *Шаг 1 из 2: Время ежедневного дайджеста*\n\n"
            "Все расчеты ведутся строго по московскому времени \\(МСК\\)\\.\n"
            "Введите желаемое время доставки дайджеста в формате *ЧЧ:ММ*:\n\n"
            "Примеры: `19:00`, `09:30`, `22:15`"
        ),
        TextInput(
            id="onboarding_time_input",
            type_factory=validate_time_format,
            on_success=on_time_input_success,
            on_error=on_time_input_error,
        ),
        parse_mode="MarkdownV2",
        state=OnboardingSG.delivery_time,
    ),
    # Окно 2: Google Sheets со ссылкой на шаблон
    Window(
        Format(
            "📊 *Шаг 2 из 2: Подключение Google Таблицы*\n\n"
            "Вы можете синхронизировать бота со своей Google Таблицей релизов "
            "или вести отслеживание вручную\\.\n\n"
            "[👉 Официальный эталонный шаблон Google Таблицы]({template_url})\n\n"
            "Для подключения создайте копию шаблона и привяжите её командами:\n"
            "1\\. `/auth` — авторизация Google\n"
            "2\\. `/code ВАШ_КОД` — отправка кода\n"
            "3\\. `/sheet ССЫЛКА` — привязка таблицы\n\n"
            "_Вы можете завершить настройку сейчас и привязать таблицу позже в любое время\\._"
        ),
        Button(Const("✅ Завершить настройку"), id="finish_onboarding", on_click=on_skip_google),
        getter=get_onboarding_google_data,
        parse_mode="MarkdownV2",
        state=OnboardingSG.google_setup,
    ),
)
