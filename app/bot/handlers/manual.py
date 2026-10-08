"""Обработчики принудительного обновления и ручных действий (/sync)."""
from __future__ import annotations

import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.digest import format_digest_html
from app.services.tracker import TrackerService

logger = logging.getLogger(__name__)
manual_router = Router(name="manual_router")


@manual_router.message(Command("sync"))
async def cmd_sync(message: Message, session: AsyncSession) -> None:
    """Обработчик команды /sync — запуск немедленной проверки обновлений серий."""
    if not message.from_user:
        return

    user_id = message.from_user.id
    await message.answer("🔍 <i>Сверяем обновления серий с Shikimori и Google Таблицей...</i>", parse_mode="HTML")

    tracker = TrackerService(
        session=session,
        encryption_key=settings.encryption_key,
    )

    try:
        deltas = await tracker.check_user_updates(user_id=user_id)
        digest_text = format_digest_html(deltas)
        await message.answer(digest_text, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as exc:
        logger.error("Ошибка при выполнении /sync для пользователя %d: %s", user_id, exc)
        await message.answer(
            f"⚠️ <b>Произошла ошибка при сверке обновлений:</b>\n<code>{exc}</code>",
            parse_mode="HTML",
        )
