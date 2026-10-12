"""Unit-тесты для app/services/digest.py — форматирование дайджестов для Telegram MarkdownV2."""
from __future__ import annotations

from app.services.digest import TitleUpdateDelta, format_digest_markdown


class TestDigestFormatter:
    """Тестирование форматирования MarkdownV2-дайджеста."""

    def test_format_empty_deltas_returns_nothing_new_message(self) -> None:
        """Если обновлений нет, возвращается аккуратное статусное сообщение."""
        result = format_digest_markdown([])
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

        result = format_digest_markdown([delta])

        assert "Клинок, рассекающий демонов" in result
        assert "[Клинок, рассекающий демонов](https://shikimori.one/animes/38000)" in result
        assert "*6* серия" in result
        assert "было 5/11" in result

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

        result = format_digest_markdown([delta1, delta2])

        assert "Тайтл А" in result
        assert "Тайтл Б" in result
        assert r"\+2" in result or "12" in result
        assert r"\?" in result  # total unknown escaped

    def test_markdown_escaping_in_title(self) -> None:
        """Экранирование спецсимволов MarkdownV2 в названии тайтла."""
        delta = TitleUpdateDelta(
            title_name_ru="Fate/stay night [Heaven's Feel] & Extra (Movie 1)!",
            shiki_id=100,
            old_episodes_aired=0,
            new_episodes_aired=1,
            total_episodes=1,
            shikimori_url="https://shikimori.one/animes/100",
        )

        result = format_digest_markdown([delta])

        assert r"\[Heaven's Feel\]" in result
        assert r"\(Movie 1\)\!" in result

    def test_format_debts_only(self) -> None:
        """Форматирование дайджеста только с блоком забытых заливок (долгов)."""
        from app.services.digest import TitleDebtItem

        debt = TitleDebtItem(
            title_name_ru="Магическая битва",
            shiki_id=40748,
            uploaded_episodes=2,
            aired_episodes=5,
            total_episodes=24,
            shikimori_url="https://shikimori.one/animes/40748",
        )

        result = format_digest_markdown(deltas=[], debts=[debt])

        assert "Забыли залить" in result
        assert "Магическая битва" in result
        assert r"отстаёт *3\-5* сер" in result
        assert "залито 2, вышло 5/24" in result
        assert "Вышли новые серии" not in result

    def test_format_single_debt_episode(self) -> None:
        """Форматирование долга ровно в одну серию (без дефиса в номере)."""
        from app.services.digest import TitleDebtItem

        debt = TitleDebtItem(
            title_name_ru="Блич",
            shiki_id=269,
            uploaded_episodes=7,
            aired_episodes=8,
            total_episodes=13,
            shikimori_url="https://shikimori.one/animes/269",
        )

        result = format_digest_markdown(deltas=[], debts=[debt])

        assert "отстаёт *8* сер" in result

    def test_format_combined_deltas_and_debts(self) -> None:
        """Форматирование комбинированного дайджеста с новыми сериями и долгами."""
        from app.services.digest import TitleDebtItem

        delta = TitleUpdateDelta(
            title_name_ru="Тайтл Новый",
            shiki_id=1,
            old_episodes_aired=1,
            new_episodes_aired=2,
            total_episodes=12,
            shikimori_url="https://shikimori.one/animes/1",
        )
        debt = TitleDebtItem(
            title_name_ru="Тайтл Долг",
            shiki_id=2,
            uploaded_episodes=0,
            aired_episodes=3,
            total_episodes=None,
            shikimori_url="https://shikimori.one/animes/2",
        )

        result = format_digest_markdown(deltas=[delta], debts=[debt])

        assert "Вышли новые серии за сегодня" in result
        assert "Тайтл Новый" in result
        assert "Забыли залить" in result
        assert "Тайтл Долг" in result
        assert r"отстаёт *1\-3* сер" in result
