"""Диалог настроек пользователя на aiogram-dialog.

Функционал:
1. Информационная сводная карточка параметров пользователя (время по МСК, статус Google Таблицы).
2. Настройка времени рассылки дайджеста (формат ЧЧ:ММ с regex-валидацией).
3. Умное управление Google Таблицей (статус, эталонный шаблон, смена и отключение).
4. Управление тайтлами в игноре напоминаний о долгах.
"""
from __future__ import annotations

import datetime
import logging
import re
from typing import Any, Dict

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.kbd import Button, Row, ScrollingGroup, Select
from aiogram_dialog.widgets.text import Const, Format
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.utils import escape_md_v2, escape_md_v2_url
from app.db.models import GoogleCredentials, TrackedTitle, User

logger = logging.getLogger(__name__)

TIME_REGEX = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
SHEETS_TEMPLATE_URL = "https://docs.google.com/spreadsheets/d/1wiDiRPt_zliosdTpC9R-1tREAy1x5h_OnDBQN_sb3Lc/edit?usp=sharing"


class SettingsSG(StatesGroup):
    """Состояния диалога настроек."""

    main = State()
    change_time = State()
    google_sheets = State()
    ignored_titles = State()


# ---------------------------------------------------------------------------
# Валидаторы
# ---------------------------------------------------------------------------


def validate_time_format(text: str) -> str:
    """Проверяет строку времени на соответствие формату ЧЧ:ММ (00:00 - 23:59).

    Raises:
        ValueError: Если формат не соответствует.
    """
    clean_text = text.strip()
    if not TIME_REGEX.match(clean_text):
        raise ValueError("Неверный формат времени. Используйте ЧЧ:ММ (например, 19:30 или 09:00)")
    return clean_text


# ---------------------------------------------------------------------------
# Геттеры данных
# ---------------------------------------------------------------------------


async def get_settings_main_data(dialog_manager: DialogManager, **kwargs: Any) -> Dict[str, Any]:
    """Геттер сводной информации для главного экрана настроек."""
    middleware_data = dialog_manager.middleware_data
    session: AsyncSession = middleware_data["session"]
    user_event = dialog_manager.event.from_user
    user_id = user_event.id if user_event else 0

    user = await session.get(User, user_id)
    time_str = user.delivery_time.strftime("%H:%M") if user and user.delivery_time else "19:00"

    creds_stmt = select(GoogleCredentials).where(GoogleCredentials.user_id == user_id)
    creds_res = await session.execute(creds_stmt)
    creds = creds_res.scalar_one_or_none()

    is_sheet_connected = bool(creds and creds.spreadsheet_id)
    sheet_id = creds.spreadsheet_id if is_sheet_connected else "Не привязана"

    # Количество игнорируемых тайтлов
    ignored_stmt = select(TrackedTitle).where(
        TrackedTitle.user_id == user_id,
        TrackedTitle.ignore_reminders.is_(True),
    )
    ignored_res = await session.execute(ignored_stmt)
    ignored_count = len(ignored_res.scalars().all())

    return {
        "delivery_time": escape_md_v2(time_str),
        "is_sheet_connected": is_sheet_connected,
        "sheet_status": escape_md_v2("Подключена" if is_sheet_connected else "Не подключена"),
        "sheet_id": escape_md_v2(sheet_id),
        "ignored_count": ignored_count,
    }


async def get_sheets_screen_data(dialog_manager: DialogManager, **kwargs: Any) -> Dict[str, Any]:
    """Геттер данных экрана управления Google Sheets."""
    middleware_data = dialog_manager.middleware_data
    session: AsyncSession = middleware_data["session"]
    user_event = dialog_manager.event.from_user
    user_id = user_event.id if user_event else 0

    creds_stmt = select(GoogleCredentials).where(GoogleCredentials.user_id == user_id)
    creds_res = await session.execute(creds_stmt)
    creds = creds_res.scalar_one_or_none()

    is_connected = bool(creds and creds.spreadsheet_id)
    sheet_url = (
        f"https://docs.google.com/spreadsheets/d/{creds.spreadsheet_id}/edit"
        if is_connected
        else ""
    )

    return {
        "is_connected": is_connected,
        "sheet_id": escape_md_v2(creds.spreadsheet_id if is_connected else ""),
        "sheet_url": escape_md_v2_url(sheet_url),
        "template_url": escape_md_v2_url(SHEETS_TEMPLATE_URL),
    }


async def get_ignored_titles_data(dialog_manager: DialogManager, **kwargs: Any) -> Dict[str, Any]:
    """Геттер списка тайтлов, исключенных из напоминаний."""
    middleware_data = dialog_manager.middleware_data
    session: AsyncSession = middleware_data["session"]
    user_event = dialog_manager.event.from_user
    user_id = user_event.id if user_event else 0

    stmt = select(TrackedTitle).where(
        TrackedTitle.user_id == user_id,
        TrackedTitle.ignore_reminders.is_(True),
    ).order_by(TrackedTitle.title_name_ru)
    result = await session.execute(stmt)
    titles = result.scalars().all()

    items = [
        {
            "id": str(t.id),
            "name": escape_md_v2(t.title_name_ru),
        }
        for t in titles
    ]

    return {
        "items": items,
        "count": len(items),
        "has_items": bool(items),
    }


# ---------------------------------------------------------------------------
# Обработчики событий
# ---------------------------------------------------------------------------


async def on_time_input_success(
    event: Message,
    widget: Any,
    manager: DialogManager,
    time_str: str,
) -> None:
    """Успешный ввод времени рассылки."""
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

    await event.answer(f"✅ Время рассылки успешно сохранено: *{escape_md_v2(time_str)}* \\(МСК\\)", parse_mode="MarkdownV2")
    await manager.switch_to(SettingsSG.main)


async def on_time_input_error(
    event: Message,
    widget: Any,
    manager: DialogManager,
    error: ValueError,
) -> None:
    """Ошибка валидации ввода времени."""
    await event.answer(
        "⚠️ *Некорректный формат времени\\!*\n\n"
        "Пожалуйста, введите время в формате *ЧЧ:ММ* от 00:00 до 23:59\\.\n"
        "Примеры: `19:00`, `09:30`, `22:15`\\.",
        parse_mode="MarkdownV2",
    )


async def on_disconnect_sheets(
    event: CallbackQuery,
    button: Button,
    manager: DialogManager,
) -> None:
    """Отключение привязанной Google Таблицы."""
    middleware_data = manager.middleware_data
    session: AsyncSession = middleware_data["session"]
    user_id = event.from_user.id if event.from_user else 0

    creds_stmt = select(GoogleCredentials).where(GoogleCredentials.user_id == user_id)
    creds_res = await session.execute(creds_stmt)
    creds = creds_res.scalar_one_or_none()

    if creds:
        creds.spreadsheet_id = None
        await session.commit()

    await event.answer("Google Таблица успешно отключена!")
    await manager.switch_to(SettingsSG.main)


async def on_restore_reminders(
    event: CallbackQuery,
    widget: Any,
    manager: DialogManager,
    item_id: str,
) -> None:
    """Возврат тайтла в напоминания (выключение игнора)."""
    middleware_data = manager.middleware_data
    session: AsyncSession = middleware_data["session"]

    try:
        title_id = int(item_id)
        title = await session.get(TrackedTitle, title_id)
        if title:
            title.ignore_reminders = False
            await session.commit()
            await event.answer(f"Тайтл '{title.title_name_ru}' возвращен в напоминания!")
    except Exception as exc:
        logger.error("Ошибка возврата тайтла из игнора %s: %s", item_id, exc)
        await event.answer("Произошла ошибка при обновлении статуса тайтла.")


async def on_close_settings(
    event: CallbackQuery,
    button: Button,
    manager: DialogManager,
) -> None:
    """Закрытие меню настроек."""
    await manager.done()


# ---------------------------------------------------------------------------
# Описание диалога настроек
# ---------------------------------------------------------------------------


settings_dialog = Dialog(
    # Окно 1: Главное меню настроек
    Window(
        Format(
            "⚙️ *Настройки Shiki\\-Helper*\n\n"
            "📋 *Текущие параметры:*\n"
            "• Время дайджеста: *{delivery_time}* \\(МСК\\)\n"
            "• Google Таблица: *{sheet_status}*\n"
            "• Тайтлов в игноре напоминаний: *{ignored_count}*\n\n"
            "Выберите раздел для изменения:"
        ),
        Row(
            Button(Const("⏰ Время рассылки"), id="btn_to_time", on_click=lambda c, b, m: m.switch_to(SettingsSG.change_time)),
            Button(Const("📊 Google Таблица"), id="btn_to_sheets", on_click=lambda c, b, m: m.switch_to(SettingsSG.google_sheets)),
        ),
        Button(Const("🔕 Игнорируемые тайтлы"), id="btn_to_ignored", on_click=lambda c, b, m: m.switch_to(SettingsSG.ignored_titles)),
        Button(Const("◀️ Закрыть"), id="btn_close_settings", on_click=on_close_settings),
        getter=get_settings_main_data,
        parse_mode="MarkdownV2",
        state=SettingsSG.main,
    ),
    # Окно 2: Изменение времени рассылки
    Window(
        Const(
            "⏰ *Настройка времени дайджеста*\n\n"
            "Все расчеты ведутся строго по московскому времени \\(МСК\\)\\.\n"
            "Введите желаемое время доставки в формате *ЧЧ:ММ*:\n\n"
            "Примеры: `12:00`, `19:30`, `22:00`"
        ),
        TextInput(
            id="time_input",
            type_factory=validate_time_format,
            on_success=on_time_input_success,
            on_error=on_time_input_error,
        ),
        Button(Const("◀️ Назад"), id="btn_back_to_main_from_time", on_click=lambda c, b, m: m.switch_to(SettingsSG.main)),
        parse_mode="MarkdownV2",
        state=SettingsSG.change_time,
    ),
    # Окно 3: Умный экран Google Sheets
    Window(
        Format(
            "📊 *Google Таблица релизов*\n\n"
            "Статус: ✅ *Подключена*\n"
            "ID таблицы: `{sheet_id}`\n\n"
            "[👉 Открыть вашу таблицу в Google Sheets]({sheet_url})\n\n"
            "Чтобы изменить таблицу, воспользуйтесь командой:\n"
            "`/sheet ССЫЛКА_ИЛИ_ID`\n\n"
            "[📋 Эталонный шаблон таблицы]({template_url})",
            when="is_connected",
        ),
        Format(
            "📊 *Google Таблица релизов*\n\n"
            "Статус: ❌ *Не подключена*\n\n"
            "Для автоматической синхронизации серий привяжите вашу таблицу:\n"
            "1\\. Авторизуйтесь через `/auth`\n"
            "2\\. Отправьте полученный код через `/code КОД`\n"
            "3\\. Привяжите таблицу через `/sheet ССЫЛКА`\n\n"
            "[👉 Скачать официальный эталонный шаблон]({template_url})",
            when=lambda data, *_: not data.get("is_connected"),
        ),
        Button(
            Const("🚫 Отключить таблицу"),
            id="btn_disconnect_sheet",
            on_click=on_disconnect_sheets,
            when="is_connected",
        ),
        Button(Const("◀️ Назад"), id="btn_back_to_main_from_sheets", on_click=lambda c, b, m: m.switch_to(SettingsSG.main)),
        getter=get_sheets_screen_data,
        parse_mode="MarkdownV2",
        state=SettingsSG.google_sheets,
    ),
    # Окно 4: Игнорируемые тайтлы
    Window(
        Format(
            "🔕 *Игнорируемые тайтлы ({count})*\n\n"
            "По этим релизам бот не отправляет напоминания о забытых заливках\\.\n"
            "Нажмите на тайтл, чтобы вернуть его в напоминания:"
        ),
        Const("Список пуст — все тайтлы отслеживаются в обычном режиме\\.", when=lambda data, *_: not data.get("has_items")),
        ScrollingGroup(
            Select(
                Format("🔔 {item[name]}"),
                id="select_restore_title",
                item_id_getter=lambda x: x["id"],
                items="items",
                on_click=on_restore_reminders,
            ),
            id="ignored_pager",
            width=1,
            height=6,
            when="has_items",
        ),
        Button(Const("◀️ Назад"), id="btn_back_to_main_from_ignored", on_click=lambda c, b, m: m.switch_to(SettingsSG.main)),
        getter=get_ignored_titles_data,
        parse_mode="MarkdownV2",
        state=SettingsSG.ignored_titles,
    ),
)
