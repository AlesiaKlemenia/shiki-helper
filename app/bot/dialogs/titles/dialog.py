"""Диалог просмотра и поиска тайтлов пользователя."""
from __future__ import annotations

import logging
from typing import Any, Dict

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.kbd import Button, Row, ScrollingGroup, Select
from aiogram_dialog.widgets.text import Const, Format
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.utils import escape_md_v2
from app.db.models import TrackedTitle
from app.services.search import SearchService

logger = logging.getLogger(__name__)


class TitlesSG(StatesGroup):
    """Состояния диалога просмотра и поиска тайтлов."""

    list_titles = State()
    search_input = State()
    title_detail = State()


async def get_titles_data(dialog_manager: DialogManager, **kwargs: Any) -> Dict[str, Any]:
    """Геттер данных для окна со списком тайтлов."""
    middleware_data = dialog_manager.middleware_data
    session: AsyncSession = middleware_data["session"]
    user = dialog_manager.event.from_user
    user_id = user.id if user else 0

    query = dialog_manager.dialog_data.get("search_query", "")

    search_service = SearchService(session)
    titles = await search_service.search_user_titles(user_id=user_id, query=query)

    titles_list = [
        {
            "id": str(t.id),
            "name": t.title_name_ru,
            "status": t.status_in_table,
            "episodes": f"{t.last_episodes_aired}/{t.total_episodes or '?'}",
        }
        for t in titles
    ]

    return {
        "titles": titles_list,
        "count": len(titles_list),
        "search_query": escape_md_v2(query),
        "is_search": bool(query),
    }


async def get_title_detail_data(dialog_manager: DialogManager, **kwargs: Any) -> Dict[str, Any]:
    """Геттер данных для окна детальной информации о выбранном тайтле."""
    middleware_data = dialog_manager.middleware_data
    session: AsyncSession = middleware_data["session"]
    title_id_str = dialog_manager.dialog_data.get("selected_title_id")

    if not title_id_str:
        return {"found": False}

    try:
        title_id = int(title_id_str)
        title = await session.get(TrackedTitle, title_id)
        if not title:
            return {"found": False}

        updated_str = title.updated_at.strftime("%d.%m.%Y %H:%M") if title.updated_at else "—"
        ignore_reminders = bool(title.ignore_reminders)
        reminders_btn_text = "🔔 Включить напоминания" if ignore_reminders else "🔕 Не напоминать о долгах"

        return {
            "found": True,
            "name": escape_md_v2(title.title_name_ru),
            "status": escape_md_v2(title.status_in_table),
            "episodes": escape_md_v2(f"{title.last_episodes_aired}/{title.total_episodes or '?'}"),
            "shiki_id": escape_md_v2(str(title.shiki_id or "—")),
            "table_row": escape_md_v2(str(title.row_index if title.row_index is not None else "—")),
            "updated_at": escape_md_v2(updated_str),
            "ignore_reminders": ignore_reminders,
            "reminders_btn_text": escape_md_v2(reminders_btn_text),
        }
    except Exception as exc:
        logger.error("Ошибка загрузки деталей тайтла %s: %s", title_id_str, exc)
        return {"found": False}


async def on_toggle_reminders(
    event: CallbackQuery,
    button: Button,
    manager: DialogManager,
) -> None:
    """Переключение флага ignore_reminders для выбранного тайтла."""
    middleware_data = manager.middleware_data
    session: AsyncSession = middleware_data["session"]
    title_id_str = manager.dialog_data.get("selected_title_id")

    if not title_id_str:
        return

    try:
        title_id = int(title_id_str)
        title = await session.get(TrackedTitle, title_id)
        if title:
            title.ignore_reminders = not bool(title.ignore_reminders)
            await session.commit()
            status_text = "отключены" if title.ignore_reminders else "включены"
            await event.answer(f"Напоминания о долгах {status_text}!")
    except Exception as exc:
        logger.error("Ошибка переключения ignore_reminders для тайтла %s: %s", title_id_str, exc)
        await event.answer("⚠️ Не удалось обновить статус напоминаний.")


async def on_title_selected(
    event: CallbackQuery,
    widget: Any,
    manager: DialogManager,
    item_id: str,
) -> None:
    """Обработчик выбора конкретного тайтла из списка."""
    manager.dialog_data["selected_title_id"] = item_id
    await manager.switch_to(TitlesSG.title_detail)


async def on_search_button(
    event: CallbackQuery,
    button: Button,
    manager: DialogManager,
) -> None:
    """Переход к окну ввода поискового запроса."""
    await manager.switch_to(TitlesSG.search_input)


async def on_reset_search(
    event: CallbackQuery,
    button: Button,
    manager: DialogManager,
) -> None:
    """Сброс активного поискового фильтра."""
    manager.dialog_data["search_query"] = ""
    await manager.switch_to(TitlesSG.list_titles)


async def on_search_submitted(
    event: Message,
    widget: Any,
    manager: DialogManager,
    text: str,
) -> None:
    """Обработчик ввода текста для поиска."""
    manager.dialog_data["search_query"] = text.strip()
    await manager.switch_to(TitlesSG.list_titles)


async def on_back_to_list(
    event: CallbackQuery,
    button: Button,
    manager: DialogManager,
) -> None:
    """Возврат в список тайтлов."""
    await manager.switch_to(TitlesSG.list_titles)


async def on_close_dialog(
    event: CallbackQuery,
    button: Button,
    manager: DialogManager,
) -> None:
    """Закрытие диалога тайтлов."""
    await manager.done()


titles_dialog = Dialog(
    # Окно 1: Список тайтлов с пагинацией и поиском
    Window(
        Format("📋 *Ваши отслеживаемые тайтлы ({count}):*\n"),
        Format("_🔍 Фильтр: «{search_query}»_\n", when="is_search"),
        ScrollingGroup(
            Select(
                Format("🎬 {item[name]} ({item[episodes]})"),
                id="select_title",
                item_id_getter=lambda x: x["id"],
                items="titles",
                on_click=on_title_selected,
            ),
            id="titles_pager",
            width=1,
            height=6,
        ),
        Row(
            Button(Const("🔍 Поиск"), id="btn_search", on_click=on_search_button),
            Button(Const("❌ Сбросить фильтр"), id="btn_reset", on_click=on_reset_search, when="is_search"),
        ),
        Button(Const("◀️ Закрыть"), id="btn_close", on_click=on_close_dialog),
        getter=get_titles_data,
        parse_mode="MarkdownV2",
        state=TitlesSG.list_titles,
    ),
    # Окно 2: Ввод поискового запроса
    Window(
        Const("🔍 *Поиск тайтлов*\n\nВведите название \\(или его часть\\) для быстрого поиска:"),
        TextInput(
            id="search_text_input",
            on_success=on_search_submitted,
        ),
        Button(Const("◀️ Отмена"), id="btn_cancel_search", on_click=on_back_to_list),
        parse_mode="MarkdownV2",
        state=TitlesSG.search_input,
    ),
    # Окно 3: Детальная информация о тайтле
    Window(
        Format(
            "🎬 *{name}*\n\n"
            "📊 Статус в таблице: *{status}*\n"
            "📺 Серии: *{episodes}*\n"
            "🔗 Shikimori ID: `{shiki_id}`\n"
            "📑 Строка в таблице: `{table_row}`\n"
            "🕒 Обновлено: {updated_at}",
            when="found",
        ),
        Const("⚠️ Тайтл не найден или был удален\\.", when=lambda data, *_: not data.get("found")),
        Button(
            Format("{reminders_btn_text}"),
            id="btn_toggle_reminders",
            on_click=on_toggle_reminders,
            when="found",
        ),
        Button(Const("◀️ Назад к списку"), id="btn_back_list", on_click=on_back_to_list),
        getter=get_title_detail_data,
        parse_mode="MarkdownV2",
        state=TitlesSG.title_detail,
    ),
)
