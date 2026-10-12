"""Обработчик входящих сообщений с логами загрузки субтитров."""
from __future__ import annotations

import logging
from aiogram import Router
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.utils import escape_md_v2
from app.clients.google_sheets import GoogleSheetsClient, format_episodes_cell
from app.config import settings
from app.db.models import GoogleCredentials, TrackedTitle
from app.services.subtitles_log import SubtitlesLogParser

logger = logging.getLogger(__name__)

subtitles_router = Router(name="subtitles_router")


@subtitles_router.message(lambda msg: SubtitlesLogParser.is_subtitles_log(msg.text))
async def handle_subtitles_log_message(message: Message, session: AsyncSession) -> None:
    """Обрабатывает входящее сообщение с логом заливки субтитров."""
    if not message.from_user:
        return

    user_id = message.from_user.id
    raw_text = message.text or ""

    payload = SubtitlesLogParser.parse(raw_text)
    if not payload:
        logger.warning("Лог субтитров обнаружен, но не удалось извлечь shiki_id или серию: %s", raw_text)
        await message.answer(
            "⚠️ *Не удалось распознать лог субтитров\\.*\n\n"
            "Убедитесь, что в сообщении указан *Shikimori ID* и *номер серии* \\(например, `Путь: 40748/3/...` или `Серия: 3`\\)\\.",
            parse_mode="MarkdownV2",
        )
        return

    try:
        # 1. Поиск тайтла в БД пользователя
        stmt = select(TrackedTitle).where(
            TrackedTitle.user_id == user_id,
            TrackedTitle.shiki_id == payload.shiki_id,
        )
        result = await session.execute(stmt)
        title = result.scalar_one_or_none()

        if not title:
            safe_id = escape_md_v2(str(payload.shiki_id))
            await message.answer(
                f"ℹ️ Тайтл с ID `{safe_id}` не найден в вашем списке отслеживаемых релизов\\.\n"
                f"Серия: *{payload.episode_num}*",
                parse_mode="MarkdownV2",
            )
            return

        old_status = title.status_in_table
        new_status = old_status

        # 2. Если статус был «Анонс» или «В планах» -> переводим в «В работе»
        if old_status in {"Анонс", "В планах"}:
            new_status = "В работе"
            title.status_in_table = new_status

        # 3. Обновляем максимальный номер залитой/вышедшей серии
        title.last_episodes_aired = max(title.last_episodes_aired, payload.episode_num)
        await session.commit()

        # 4. Обновление личной Google Таблицы пользователя (при наличии)
        creds_stmt = select(GoogleCredentials).where(GoogleCredentials.user_id == user_id)
        creds_res = await session.execute(creds_stmt)
        creds = creds_res.scalar_one_or_none()

        sheet_updated = False
        team_sheet_updated = False

        if creds:
            try:
                sheets_client = GoogleSheetsClient(
                    client_id=creds.client_id,
                    client_secret=creds.client_secret,
                    encrypted_refresh_token=creds.encrypted_refresh_token,
                    encryption_key=settings.encryption_key,
                )

                # 4a. Обновление личной Google Таблицы
                if creds.spreadsheet_id and title.row_index:
                    formatted_episodes = format_episodes_cell(
                        aired=title.last_episodes_aired,
                        total=title.total_episodes,
                    )
                    status_to_update = new_status if new_status != old_status else None
                    await sheets_client.update_title_row(
                        spreadsheet_id=creds.spreadsheet_id,
                        row_index=title.row_index,
                        status=status_to_update,
                        episodes_text=formatted_episodes,
                    )
                    sheet_updated = True

                # 4b. Обновление командной Google Таблицы (при наличии team_spreadsheet_id)
                if settings.team_spreadsheet_id:
                    team_sheet_updated = await sheets_client.find_and_update_team_subtitles(
                        spreadsheet_id=settings.team_spreadsheet_id,
                        shiki_id=payload.shiki_id,
                        episode_num=payload.episode_num,
                    )

            except Exception as sheet_err:
                logger.error("Ошибка при обновлении Google Таблиц: %s", sheet_err)

        # 5. Формирование ответа пользователю
        safe_name = escape_md_v2(title.title_name_ru)
        safe_ep = escape_md_v2(str(payload.episode_num))
        safe_status = escape_md_v2(new_status)
        total_str = escape_md_v2(str(title.total_episodes)) if title.total_episodes and title.total_episodes > 0 else "\\?"

        status_change_note = ""
        if new_status != old_status:
            safe_old = escape_md_v2(old_status)
            status_change_note = f"\n🔄 Статус изменен: *{safe_old}* ➔ *{safe_status}*"

        sheet_notes = []
        if sheet_updated:
            sheet_notes.append("📊 Личная таблица: *обновлена*")
        if team_sheet_updated:
            sheet_notes.append("👥 Командная таблица: *обновлена*")

        sheet_note_str = ("\n" + "\n".join(sheet_notes)) if sheet_notes else ""

        reply_text = (
            f"📥 *Лог сабов успешно обработан\\!*\n\n"
            f"🎬 Тайтл: *{safe_name}*\n"
            f"📺 Залита серия: *{safe_ep}* \\(всего в базе: {title.last_episodes_aired}/{total_str}\\)"
            f"{status_change_note}"
            f"{sheet_note_str}"
        )

        await message.answer(reply_text, parse_mode="MarkdownV2")

    except Exception as exc:
        logger.error("Критическая ошибка при обработке лога субтитров: %s", exc)
        safe_exc = escape_md_v2(str(exc))
        await message.answer(
            f"⚠️ *Ошибка при сохранении лога сабов:*\n`{safe_exc}`",
            parse_mode="MarkdownV2",
        )
