"""Unit-тесты для app/bot/utils.py — экранирование MarkdownV2."""
from __future__ import annotations

from app.bot.utils import escape_md_v2, escape_md_v2_url


class TestEscapeMarkdownV2:
    """Тестирование экранирования Telegram MarkdownV2."""

    def test_escape_empty_string(self) -> None:
        """Пустая строка или None возвращают пустую строку."""
        assert escape_md_v2("") == ""
        assert escape_md_v2(None) == ""

    def test_escape_special_characters(self) -> None:
        """Все 18 спецсимволов MarkdownV2 должны экранироваться бэкслешем."""
        raw = "_ * [ ] ( ) ~ > # + - = | { } . ! \\"
        escaped = escape_md_v2(raw)
        expected = r"\_ \* \[ \] \( \) \~ \> \# \+ \- \= \| \{ \} \. \! \\"
        assert escaped == expected

    def test_escape_regular_alphanumeric(self) -> None:
        """Буквы и цифры на кириллице и латинице не меняются."""
        text = "Привет мир Hello World 12345"
        assert escape_md_v2(text) == text

    def test_escape_complex_anime_title(self) -> None:
        """Сложное название тайтла со скобками, точками и восклицательными знаками."""
        raw = "Re:Zero - Starting Life in Another World (Season 2) Part 1!"
        escaped = escape_md_v2(raw)
        assert r"\-" in escaped
        assert r"\(" in escaped
        assert r"\)" in escaped
        assert r"\!" in escaped

    def test_escape_md_v2_url(self) -> None:
        """В URL должны экранироваться только ')' и '\\'."""
        raw_url = "https://shikimori.one/animes/123(part_1)\\test"
        escaped_url = escape_md_v2_url(raw_url)
        assert r"\)" in escaped_url
        assert r"\\" in escaped_url
        assert "." in escaped_url  # Точки в URL внутри [text](url) экранировать не нужно
