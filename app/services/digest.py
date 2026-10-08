"""Сервис формирования Telegram-дайджеста об вышедших сериях аниме."""
from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Optional


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


def format_digest_html(deltas: list[TitleUpdateDelta]) -> str:
    """Форматирует список обновлений в красивое сообщение для Telegram с HTML-разметкой.

    Args:
        deltas: Список найденных обновлений.

    Returns:
        Отформатированный HTML-текст для Telegram бота.
    """
    if not deltas:
        return "✨ <b>Новых серий пока не выходило.</b>\nВсе релизы проверены, статус актуален!"

    lines: list[str] = [
        "🔔 <b>Свежие обновления серий:</b>\n"
    ]

    for item in deltas:
        safe_title = html.escape(item.title_name_ru)
        total_str = str(item.total_episodes) if item.total_episodes and item.total_episodes > 0 else "?"
        url = item.shikimori_url or f"https://shikimori.one/animes/{item.shiki_id}"

        if item.new_episodes_count > 1:
            diff_text = f"+{item.new_episodes_count} серий"
        else:
            diff_text = "новая серия"

        line = (
            f"• <a href=\"{url}\">{safe_title}</a> — <b>{item.new_episodes_aired}</b> серия "
            f"({diff_text}, было {item.old_episodes_aired}/{total_str})"
        )
        lines.append(line)

    lines.append("\n<i>Удачного просмотра и приятной озвучки/саба! 🍿</i>")
    return "\n".join(lines)
