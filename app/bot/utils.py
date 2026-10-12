"""Утилиты форматирования и экранирования сообщений для Telegram."""
from __future__ import annotations

import re

# Список спецсимволов, требующих экранирования в Telegram MarkdownV2:
# _ * [ ] ( ) ~ > # + - = | { } . ! \
MD_V2_SPECIAL_CHARS = re.compile(r"([_*\[\]()~>#+\-=|{}.!\\])")

# Внутри скобок URL для ссылок [текст](url) экранируются только ')' и '\'
MD_V2_URL_SPECIAL_CHARS = re.compile(r"([\\)])")


def escape_md_v2(text: str | None) -> str:
    """Безопасное экранирование спецсимволов для Telegram MarkdownV2.

    Args:
        text: Исходная строка для экранирования.

    Returns:
        Экранированная строка.
    """
    if not text:
        return ""
    return MD_V2_SPECIAL_CHARS.sub(r"\\\1", str(text))


def escape_md_v2_url(url: str | None) -> str:
    """Экранирование спецсимволов внутри URL-ссылки для MarkdownV2.

    Внутри скобок ссылки [текст](url) Telegram требует экранировать только ')' и '\\'.

    Args:
        url: Исходный URL.

    Returns:
        Экранированный URL.
    """
    if not url:
        return ""
    return MD_V2_URL_SPECIAL_CHARS.sub(r"\\\1", str(url))
