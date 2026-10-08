"""Сервис сверки серий (TrackerService) и двусторонней синхронизации."""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.google_sheets import GoogleSheetsClient, format_episodes_cell
from app.clients.shikimori import AnimeInfo, ShikimoriGraphQLClient
from app.db.models import GoogleCredentials, TrackedTitle
from app.services.digest import TitleUpdateDelta

logger = logging.getLogger(__name__)


class TrackerService:
    """Сервис проверки обновлений серий, синхронизации БД и Google Таблиц."""

    def __init__(
        self,
        session: AsyncSession,
        encryption_key: str,
        user_agent: str = "Shiki-Helper-Bot/1.0",
    ) -> None:
        self.session = session
        self.encryption_key = encryption_key
        self.user_agent = user_agent

    async def check_user_updates(self, user_id: int) -> list[TitleUpdateDelta]:
        """Проверяет обновления серий для конкретного пользователя.

        Шаги:
        1. Загрузка пользователя и его GoogleCredentials (если есть).
        2. Определение тайтлов: из Google Таблицы (с приоритетом) или из БД.
        3. Запрос актуального состояния эпизодов через Shikimori GraphQL.
        4. Вычисление дельты (aired_new > aired_old).
        5. Пакетное обновление Google Таблицы (при наличии).
        6. Обновление записей в таблице `tracked_titles`.
        7. Возврат списка `TitleUpdateDelta`.
        """
        # 1. Проверяем наличие Google Credentials
        stmt_creds = select(GoogleCredentials).where(GoogleCredentials.user_id == user_id)
        res_creds = await self.session.execute(stmt_creds)
        creds = res_creds.scalar_one_or_none()

        # Существующие тайтлы в БД для быстрого поиска
        stmt_titles = select(TrackedTitle).where(TrackedTitle.user_id == user_id)
        res_titles = await self.session.execute(stmt_titles)
        db_titles_map = {t.shiki_id: t for t in res_titles.scalars().all()}

        # Собираем целевые тайтлы для проверки: {shiki_id: (title_name, row_index, old_aired, status)}
        target_map: dict[int, tuple[str, Optional[int], int, str, Optional[int]]] = {}
        sheets_client: Optional[GoogleSheetsClient] = None
        spreadsheet_id: Optional[str] = None

        if creds and creds.spreadsheet_id:
            spreadsheet_id = creds.spreadsheet_id
            sheets_client = GoogleSheetsClient(
                client_id=creds.client_id,
                client_secret=creds.client_secret,
                encrypted_refresh_token=creds.encrypted_refresh_token,
                encryption_key=self.encryption_key,
            )

            sheet_rows = await sheets_client.read_releases_range(spreadsheet_id)
            for row in sheet_rows:
                shiki_id = row.extract_shiki_id()
                if not shiki_id:
                    continue

                existing = db_titles_map.get(shiki_id)
                old_aired = existing.last_episodes_aired if existing else 0
                total_episodes = existing.total_episodes if existing else None

                target_map[shiki_id] = (
                    row.title_name_ru,
                    row.row_index,
                    old_aired,
                    row.status,
                    total_episodes,
                )
        else:
            # Источник — только БД
            for t in db_titles_map.values():
                target_map[t.shiki_id] = (
                    t.title_name_ru,
                    t.row_index,
                    t.last_episodes_aired,
                    t.status_in_table,
                    t.total_episodes,
                )

        if not target_map:
            return []

        # 3. Запрос свежих данных из Shikimori
        shiki_ids = list(target_map.keys())
        async with ShikimoriGraphQLClient(user_agent=self.user_agent) as shiki_client:
            anime_infos = await shiki_client.fetch_animes_by_ids(shiki_ids)

        anime_infos_map: dict[int, AnimeInfo] = {a.id: a for a in anime_infos}

        deltas: list[TitleUpdateDelta] = []
        sheets_updates: list[tuple[int, str]] = []

        # 4. Анализ дельт
        for shiki_id, (title_name, row_idx, old_aired, status, total_eps) in target_map.items():
            info = anime_infos_map.get(shiki_id)
            if not info:
                continue

            new_aired = info.episodes_aired
            actual_total = info.episodes if info.episodes and info.episodes > 0 else total_eps

            # Обновляем или создаем запись в БД
            existing_model = db_titles_map.get(shiki_id)
            if existing_model:
                existing_model.title_name_ru = title_name
                existing_model.status_in_table = status
                existing_model.row_index = row_idx
                existing_model.total_episodes = actual_total
            else:
                existing_model = TrackedTitle(
                    user_id=user_id,
                    shiki_id=shiki_id,
                    title_name_ru=title_name,
                    status_in_table=status,
                    row_index=row_idx,
                    last_episodes_aired=old_aired,
                    total_episodes=actual_total,
                )
                self.session.add(existing_model)

            # Вышла ли новая серия?
            if new_aired > old_aired:
                existing_model.last_episodes_aired = new_aired
                deltas.append(
                    TitleUpdateDelta(
                        title_name_ru=title_name,
                        shiki_id=shiki_id,
                        old_episodes_aired=old_aired,
                        new_episodes_aired=new_aired,
                        total_episodes=actual_total,
                        shikimori_url=info.url,
                    )
                )

                # Добавляем в список на обновление ячейки в Google Sheets
                if row_idx is not None:
                    cell_val = format_episodes_cell(aired=new_aired, total=actual_total)
                    sheets_updates.append((row_idx, cell_val))

        # 5. Пакетное обновление Google Таблицы
        if sheets_client and spreadsheet_id and sheets_updates:
            try:
                await sheets_client.batch_update_episodes(
                    spreadsheet_id=spreadsheet_id,
                    updates=sheets_updates,
                )
                logger.info(
                    "Успешно обновлено %d ячеек в Google Таблице %s",
                    len(sheets_updates),
                    spreadsheet_id,
                )
            except Exception as exc:
                logger.error("Ошибка при обновлении Google Таблицы: %s", exc)

        # 6. Сохранение изменений в БД
        await self.session.commit()

        return deltas
