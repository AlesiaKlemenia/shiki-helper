"""Сервис формирования Telegram-дайджеста об вышедших сериях аниме."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.bot.utils import escape_md_v2, escape_md_v2_url


@dataclass(frozen=True, slots=True)
class TitleUpdateDelta:
    """Дельта обновления по конкретному релизу."""

    title_name_ru: str
    shiki_id: int
    old_episodes_aired: int
    new_episodes_aired: int
    total_episodes: Optional[int]
    shikimori_url: str

    @property
    def new_episodes_count(self) -> int:
        """Количество вышедших новых серий."""
        return max(0, self.new_episodes_aired - self.old_episodes_aired)


@dataclass(frozen=True, slots=True)
class TitleDebtItem:
    """Информация об отстающем тайтле (забытой заливке)."""

    title_name_ru: str
    shiki_id: int
    uploaded_episodes: int
    aired_episodes: int
    total_episodes: Optional[int]
    shikimori_url: str

    @property
    def missing_episodes_text(self) -> str:
        """Форматирует диапазон недостающих серий, например '3' или '3-5'."""
        start = self.uploaded_episodes + 1
        end = self.aired_episodes
        if start == end:
            return f"{start}"
        return f"{start}-{end}"


@dataclass(frozen=True, slots=True)
class DigestResult:
    """Результат проверки обновлений и долгов пользователя."""

    deltas: list[TitleUpdateDelta]
    debts: list[TitleDebtItem]

    @property
    def has_content(self) -> bool:
        """Есть ли новые серии или долги для отправки дайджеста."""
        return bool(self.deltas or self.debts)


def format_digest_markdown(
    deltas: list[TitleUpdateDelta],
    debts: Optional[list[TitleDebtItem]] = None,
) -> str:
    """Форматирует список обновлений и долгов в сообщение для Telegram с разметкой MarkdownV2.

    Блоки сообщения:
    1. 🆕 *Вышли новые серии за сегодня:* (при наличии deltas)
    2. ⏳ *Забыли залить (долги):* (при наличии debts)

    Args:
        deltas: Список вышедших серий.
        debts: Список отстающих тайтлов (долгов по заливке).

    Returns:
        Отформатированный MarkdownV2 текст для Telegram бота.
    """
    debts = debts or []

    if not deltas and not debts:
        return escape_md_v2("✨ Новых серий пока не выходило, долгов нет.\nВсе релизы проверены, статус актуален!")

    blocks: list[str] = []

    # Блок 1: Новые серии
    if deltas:
        delta_lines: list[str] = ["🆕 *Вышли новые серии за сегодня:*\n"]
        for item in deltas:
            safe_title = escape_md_v2(item.title_name_ru)
            total_str = escape_md_v2(str(item.total_episodes)) if item.total_episodes and item.total_episodes > 0 else "\\?"
            raw_url = item.shikimori_url or f"https://shikimori.one/animes/{item.shiki_id}"
            safe_url = escape_md_v2_url(raw_url)

            if item.new_episodes_count > 1:
                diff_text = escape_md_v2(f"+{item.new_episodes_count} серий")
            else:
                diff_text = escape_md_v2("новая серия")

            old_aired_str = escape_md_v2(str(item.old_episodes_aired))
            new_aired_str = escape_md_v2(str(item.new_episodes_aired))

            line = (
                f"• [{safe_title}]({safe_url}) — *{new_aired_str}* серия "
                f"\\({diff_text}, было {old_aired_str}/{total_str}\\)"
            )
            delta_lines.append(line)
        blocks.append("\n".join(delta_lines))

    # Блок 2: Долги по заливке
    if debts:
        debt_lines: list[str] = ["⏳ *Забыли залить \\(долги\\):*\n"]
        for debt in debts:
            safe_title = escape_md_v2(debt.title_name_ru)
            raw_url = debt.shikimori_url or f"https://shikimori.one/animes/{debt.shiki_id}"
            safe_url = escape_md_v2_url(raw_url)
            safe_missing = escape_md_v2(debt.missing_episodes_text)
            safe_uploaded = escape_md_v2(str(debt.uploaded_episodes))
            safe_aired = escape_md_v2(str(debt.aired_episodes))
            total_str = escape_md_v2(str(debt.total_episodes)) if debt.total_episodes and debt.total_episodes > 0 else "\\?"

            line = (
                f"• [{safe_title}]({safe_url}) — отстаёт *{safe_missing}* сер\\. "
                f"\\(залито {safe_uploaded}, вышло {safe_aired}/{total_str}\\)"
            )
            debt_lines.append(line)
        blocks.append("\n".join(debt_lines))

    blocks.append("_Удачного просмотра и приятной озвучки/саба\\! 🍿_")
    return "\n\n".join(blocks)


# Алиас для обратной совместимости
format_digest_html = format_digest_markdown

