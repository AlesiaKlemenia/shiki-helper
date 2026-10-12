"""Обработчики принудительного обновления и ручных действий (/sync)."""
from __future__ import annotations

import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.utils import escape_md_v2
from app.config import settings
from app.services.digest import format_digest_markdown
from app.services.tracker import TrackerService

logger = logging.getLogger(__name__)
manual_router = Router(name="manual_router")


@manual_router.message(Command("sync"))
async def cmd_sync(message: Message, session: AsyncSession) -> None:
    """Обработчик команды /sync — запуск немедленной проверки обновлений серий."""
    if not message.from_user:
        return

    user_id = message.from_user.id
    await message.answer("🔍 _Сверяем обновления серий с Shikimori и Google Таблицей\\.\\.\\._", parse_mode="MarkdownV2")

    tracker = TrackerService(
        session=session,
        encryption_key=settings.encryption_key,
    )

    try:
        result = await tracker.check_user_updates_full(user_id=user_id)
        digest_text = format_digest_markdown(result.deltas, result.debts)
        await message.answer(digest_text, parse_mode="MarkdownV2", disable_web_page_preview=True)
    except Exception as exc:
        logger.error("Ошибка при выполнении /sync для пользователя %d: %s", user_id, exc)
        safe_exc = escape_md_v2(str(exc))
        await message.answer(
            f"⚠️ *Произошла ошибка при сверке обновлений:*\n`{safe_exc}`",
            parse_mode="MarkdownV2",
        )
