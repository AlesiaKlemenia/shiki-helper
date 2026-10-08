"""Unit-тесты для app/services/digest.py — форматирование дайджестов для Telegram.

Стратегия: TDD Red Phase.
"""
from __future__ import annotations

from app.services.digest import TitleUpdateDelta, format_digest_html


class TestDigestFormatter:
    """Тестирование форматирования HTML-дайджеста."""

    def test_format_empty_deltas_returns_nothing_new_message(self) -> None:
        """Если обновлений нет, возвращается аккуратное статусное сообщение."""
        result = format_digest_html([])
        assert "Новых серий пока не выходило" in result
        assert "Все релизы проверены" in result

    def test_format_single_update(self) -> None:
        """Форматирование одного вышедшего релиза."""
        delta = TitleUpdateDelta(
            title_name_ru="Клинок, рассекающий демонов",
            shiki_id=38000,
            old_episodes_aired=5,
            new_episodes_aired=6,
            total_episodes=11,
            shikimori_url="https://shikimori.one/animes/38000",
        )

        result = format_digest_html([delta])

        assert "Клинок, рассекающий демонов" in result
        assert "https://shikimori.one/animes/38000" in result
        assert "серия <b>6</b>" in result or "<b>6</b>" in result
        assert "было 5/11" in result or "5/11" in result

    def test_format_multiple_updates(self) -> None:
        """Форматирование нескольких релизов в единый список."""
        delta1 = TitleUpdateDelta(
            title_name_ru="Тайтл А",
            shiki_id=1,
            old_episodes_aired=0,
            new_episodes_aired=1,
            total_episodes=12,
            shikimori_url="https://shikimori.one/animes/1",
        )
        delta2 = TitleUpdateDelta(
            title_name_ru="Тайтл Б",
            shiki_id=2,
            old_episodes_aired=10,
            new_episodes_aired=12,  # Вышло сразу 2 серии!
            total_episodes=None,
            shikimori_url="https://shikimori.one/animes/2",
        )

        result = format_digest_html([delta1, delta2])

        assert "Тайтл А" in result
        assert "Тайтл Б" in result
        assert "+2" in result or "12" in result
        assert "?" in result  # total unknown

    def test_html_escaping_in_title(self) -> None:
        """Экранирование спецсимволов HTML в названии тайтла."""
        delta = TitleUpdateDelta(
            title_name_ru="Fate/stay night <Heaven's Feel> & Extra",
            shiki_id=100,
            old_episodes_aired=0,
            new_episodes_aired=1,
            total_episodes=1,
            shikimori_url="https://shikimori.one/animes/100",
        )

        result = format_digest_html([delta])

        assert "&lt;Heaven" in result
        assert "Feel&gt;" in result
        assert "&amp;" in result
