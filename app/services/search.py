"""Сервис поиска тайтлов с нормализацией символов 'ё' -> 'е' и устойчивостью к ошибкам."""
from __future__ import annotations

import re
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TrackedTitle


def sanitize_search_query(raw_query: str) -> str:
    """Нормализует поисковый запрос:

    - Удаляет опасные для FTS спецсимволы.
    - Приводит буквы 'ё' и 'Ё' к 'е' и 'Е'.
    - Убирает лишние пробелы.
    """
    if not raw_query:
        return ""

    # Замена ё/Ё на е/Е
    normalized = raw_query.replace("ё", "е").replace("Ё", "Е")

    # Удаление не-буквенно-цифровых символов (оставляем буквы, цифры, дефис и пробелы)
    cleaned = re.sub(r"[^\w\s\-]", " ", normalized, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


class SearchService:
    """Сервис поиска тайтлов пользователя."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search_user_titles(
        self, user_id: int, query: str
    ) -> Sequence[TrackedTitle]:
        """Ищет тайтлы пользователя по подстроке названия с поддержкой нормализации 'ё'/'е'.

        Args:
            user_id: Telegram ID пользователя.
            query: Строка поискового запроса.

        Returns:
            Список найденных объектов TrackedTitle.
        """
        stmt = select(TrackedTitle).where(TrackedTitle.user_id == user_id)

        clean_query = sanitize_search_query(query)
        if not clean_query:
            # Пустой запрос — возвращаем все отслеживаемые тайтлы пользователя
            stmt = stmt.order_by(TrackedTitle.title_name_ru)
            result = await self.session.execute(stmt)
            return result.scalars().all()

        # Поиск по нормализованному шаблону:
        # Для поддержки поиска как с 'е', так и с 'ё' заменяем вхождение
        # и выполняем выборку всех тайтлов пользователя с последующей фильтрацией в памяти,
        # либо через SQL OR ILIKE.
        variant_e = clean_query
        variant_yo = clean_query.replace("е", "ё").replace("Е", "Ё")

        pattern_e = f"%{variant_e}%"
        pattern_yo = f"%{variant_yo}%"

        stmt = stmt.where(
            (TrackedTitle.title_name_ru.ilike(pattern_e))
            | (TrackedTitle.title_name_ru.ilike(pattern_yo))
        ).order_by(TrackedTitle.title_name_ru)

        result = await self.session.execute(stmt)
        return result.scalars().all()
