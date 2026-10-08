"""Unit-тесты для app/services/search.py — поиск тайтлов с нормализацией и fallback.

Стратегия: TDD Red Phase.
"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Base, TrackedTitle, User
from app.db.session import create_session_factory
from app.services.search import SearchService, sanitize_search_query


class TestSearchQuerySanitizer:
    """Тестирование нормализации букв 'ё' -> 'е' и обработки поисковой строки."""

    def test_normalize_yo_to_ye(self) -> None:
        assert sanitize_search_query("Фрирен Провожающая") == "Фрирен Провожающая"
        assert sanitize_search_query("Всё пёстрое") == "Все пестрое"
        assert sanitize_search_query("Ёжик в тумане") == "Ежик в тумане"

    def test_strips_special_characters(self) -> None:
        query = sanitize_search_query("  Клинок! @#$*()  ")
        assert "Клинок" in query


class TestSearchService:
    """Тестирование работы SearchService на in-memory базе данных SQLite."""

    @pytest.fixture
    async def db_session(self) -> AsyncSession:
        factory = create_session_factory("sqlite+aiosqlite:///:memory:")
        async with factory() as session:
            # Создаем таблицы
            engine = session.bind
            assert engine is not None
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            # Добавляем тестового пользователя и тайтлы
            user = User(telegram_id=1001, timezone="Europe/Moscow")
            session.add(user)

            titles = [
                TrackedTitle(
                    user_id=1001,
                    shiki_id=1,
                    title_name_ru="Магическая битва",
                    status_in_table="В работе",
                ),
                TrackedTitle(
                    user_id=1001,
                    shiki_id=2,
                    title_name_ru="Провожающая в последний путь Фрирен",
                    status_in_table="В планах",
                ),
                TrackedTitle(
                    user_id=1001,
                    shiki_id=3,
                    title_name_ru="Тёмный дворецкий",
                    status_in_table="Анонс",
                ),
                TrackedTitle(
                    user_id=2002,  # Чужой пользователь
                    shiki_id=4,
                    title_name_ru="Магическая битва (чужая)",
                    status_in_table="В работе",
                ),
            ]
            session.add_all(titles)
            await session.commit()
            yield session

    @pytest.mark.asyncio
    async def test_search_by_exact_substring(self, db_session: AsyncSession) -> None:
        service = SearchService(db_session)
        results = await service.search_user_titles(user_id=1001, query="Фрирен")
        assert len(results) == 1
        assert results[0].shiki_id == 2

    @pytest.mark.asyncio
    async def test_search_with_yo_normalization(self, db_session: AsyncSession) -> None:
        """Поиск по слову 'Темный' должен находить 'Тёмный'."""
        service = SearchService(db_session)
        results = await service.search_user_titles(user_id=1001, query="Темный")
        assert len(results) == 1
        assert results[0].shiki_id == 3

    @pytest.mark.asyncio
    async def test_search_isolates_by_user_id(self, db_session: AsyncSession) -> None:
        """Поиск возвращает тайтлы строго текущего пользователя."""
        service = SearchService(db_session)
        results = await service.search_user_titles(user_id=1001, query="Магическая")
        assert len(results) == 1
        assert results[0].shiki_id == 1

    @pytest.mark.asyncio
    async def test_search_empty_query_returns_all_user_titles(
        self, db_session: AsyncSession
    ) -> None:
        service = SearchService(db_session)
        results = await service.search_user_titles(user_id=1001, query="")
        assert len(results) == 3
