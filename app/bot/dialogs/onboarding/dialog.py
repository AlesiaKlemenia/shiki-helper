"""Диалог онбординга (Onboarding Dialog) на aiogram-dialog.

Шаги:
1. Выбор часового пояса.
2. Выбор времени ежедневного дайджеста.
3. Инструкция по Google Sheets (или пропуск).
"""
from __future__ import annotations

from typing import Any

from aiogram.fsm.state import State, StatesGroup
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.kbd import Button, Row
from aiogram_dialog.widgets.text import Const


class OnboardingSG(StatesGroup):
    """Состояния мастера настройки онбординга."""

    timezone = State()
    delivery_time = State()
    google_setup = State()


async def on_timezone_selected(
    event: Any,
    button: Button,
    manager: DialogManager,
) -> None:
    """Обработчик выбора таймзоны."""
    tz = button.widget_id or "Europe/Moscow"
    manager.dialog_data["timezone"] = tz
    await manager.switch_to(OnboardingSG.delivery_time)


async def on_time_selected(
    event: Any,
    button: Button,
    manager: DialogManager,
) -> None:
    """Обработчик выбора времени дайджеста."""
    time_str = button.widget_id or "19:00"
    manager.dialog_data["delivery_time"] = time_str
    await manager.switch_to(OnboardingSG.google_setup)


async def on_skip_google(
    event: Any,
    button: Button,
    manager: DialogManager,
) -> None:
    """Пропуск настройки Google Sheets."""
    await manager.done()


onboarding_dialog = Dialog(
    # Окно 1: Часовой пояс
    Window(
        Const("🌍 <b>Шаг 1 из 3: Выберите ваш часовой пояс</b>\n\n"
              "Это нужно для точной доставки ежедневного дайджеста без задержек:"),
        Row(
            Button(Const("Москва (UTC+3)"), id="Europe/Moscow", on_click=on_timezone_selected),
            Button(Const("Киев (UTC+2)"), id="Europe/Kyiv", on_click=on_timezone_selected),
        ),
        Row(
            Button(Const("Алматы (UTC+5)"), id="Asia/Almaty", on_click=on_timezone_selected),
            Button(Const("Екатеринбург (UTC+5)"), id="Asia/Yekaterinburg", on_click=on_timezone_selected),
        ),
        state=OnboardingSG.timezone,
    ),
    # Окно 2: Время рассылки
    Window(
        Const("⏰ <b>Шаг 2 из 3: В какое время присылать дайджест?</b>\n\n"
              "Выберите удобное для вас вечернее или дневное время:"),
        Row(
            Button(Const("12:00 (Обед)"), id="12:00", on_click=on_time_selected),
            Button(Const("19:00 (Вечер)"), id="19:00", on_click=on_time_selected),
            Button(Const("22:00 (Поздно)"), id="22:00", on_click=on_time_selected),
        ),
        state=OnboardingSG.delivery_time,
    ),
    # Окно 3: Google Sheets
    Window(
        Const("📊 <b>Шаг 3 из 3: Подключение Google Таблицы</b>\n\n"
              "Вы можете синхронизировать бот со своей Google Таблицей релизов "
              "или отслеживать тайтлы вручную без таблицы.\n\n"
              "<i>Если таблицы пока нет, вы можете пропустить этот шаг и подключить её позже.</i>"),
        Button(Const("⏩ Пропустить привязку таблицы (ручной режим)"), id="skip_google", on_click=on_skip_google),
        state=OnboardingSG.google_setup,
    ),
)
