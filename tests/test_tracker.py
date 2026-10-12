"""Unit-тесты для app/services/tracker.py — бизнес-логика сверки серий и формирования дельты.

Стратегия: TDD Red Phase.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.google_sheets import SheetRow
from app.clients.shikimori import AnimeInfo
from app.db.models import Base, GoogleCredentials, TrackedTitle, User
from app.db.session import create_session_factory
from app.services.tracker import TrackerService


class TestTrackerService:
    """Тестирование TrackerService."""

    @pytest.fixture
    async def db_session(self) -> AsyncSession:
        factory = create_session_factory("sqlite+aiosqlite:///:memory:")
        async with factory() as session:
            engine = session.bind
            assert engine is not None
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            user = User(telegram_id=5001, timezone="Europe/Moscow")
            session.add(user)
            await session.commit()
            yield session

    @pytest.mark.asyncio
    async def test_tracker_sync_with_google_sheets(self, db_session: AsyncSession) -> None:
        """Сверка серий при наличии Google Таблицы: обнаружение дельты, вызов batchUpdate."""
        user_id = 5001

        # Добавляем учетные данные Google
        creds = GoogleCredentials(
            user_id=user_id,
            encrypted_refresh_token="enc_token",
            client_id="cid",
            client_secret="csec",
            scopes='["https://www.googleapis.com/auth/spreadsheets"]',
            spreadsheet_id="test_sheet_123",
        )
        # Добавляем существующий отслеживаемый тайтл в БД (старое состояние: 5 серий)
        title = TrackedTitle(
            user_id=user_id,
            shiki_id=101,
            title_name_ru="Магическая битва",
            status_in_table="В работе",
            row_index=2,
            last_episodes_aired=5,
            total_episodes=24,
        )
        db_session.add_all([creds, title])
        await db_session.commit()

        # Мокаем ответ от Google Sheets (1 строка в таблице)
        mock_sheet_rows = [
            SheetRow(
                row_index=2,
                title_name_ru="Магическая битва",
                shiki_link_or_id="https://shikimori.one/animes/101",
                status="В работе",
                current_episodes_text="5/24",
            )
        ]

        # Мокаем ответ от Shikimori (вышла 6-я серия!)
        mock_anime_infos = [
            AnimeInfo(
                id=101,
                name="Jujutsu Kaisen",
                russian="Магическая битва",
                status="ongoing",
                episodes=24,
                episodes_aired=6,
                url="https://shikimori.one/animes/101",
            )
        ]

        with patch("app.services.tracker.GoogleSheetsClient") as mock_sheets_cls, \
             patch("app.services.tracker.ShikimoriGraphQLClient") as mock_shiki_cls:

            mock_sheets_inst = MagicMock()
            mock_sheets_inst.read_releases_range = AsyncMock(return_value=mock_sheet_rows)
            mock_sheets_inst.batch_update_episodes = AsyncMock(return_value=1)
            mock_sheets_cls.return_value = mock_sheets_inst

            mock_shiki_inst = MagicMock()
            mock_shiki_inst.__aenter__ = AsyncMock(return_value=mock_shiki_inst)
            mock_shiki_inst.__aexit__ = AsyncMock(return_value=None)
            mock_shiki_inst.fetch_animes_by_ids = AsyncMock(return_value=mock_anime_infos)
            mock_shiki_cls.return_value = mock_shiki_inst

            tracker = TrackerService(
                session=db_session,
                encryption_key="dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ=",
            )
            deltas = await tracker.check_user_updates(user_id=user_id)

            # Проверяем найденную дельту
            assert len(deltas) == 1
            assert deltas[0].shiki_id == 101
            assert deltas[0].old_episodes_aired == 5
            assert deltas[0].new_episodes_aired == 6
            assert deltas[0].new_episodes_count == 1

            # Проверяем, что в Google Sheets отправлено обновление для строки 2
            mock_sheets_inst.batch_update_episodes.assert_awaited_once_with(
                spreadsheet_id="test_sheet_123",
                updates=[(2, "6/24")],
            )

            # Проверяем, что в БД обновилось last_episodes_aired
            await db_session.refresh(title)
            assert title.last_episodes_aired == 6

    @pytest.mark.asyncio
    async def test_tracker_sync_without_google_sheets(self, db_session: AsyncSession) -> None:
        """Сверка серий только по БД, если у пользователя нет Google Таблицы."""
        user_id = 5001

        title = TrackedTitle(
            user_id=user_id,
            shiki_id=202,
            title_name_ru="Атака титанов",
            status_in_table="В работе",
            row_index=None,
            last_episodes_aired=10,
            total_episodes=12,
        )
        db_session.add(title)
        await db_session.commit()

        mock_anime_infos = [
            AnimeInfo(
                id=202,
                name="Shingeki no Kyojin",
                russian="Атака титанов",
                status="released",
                episodes=12,
                episodes_aired=12,  # Вышло 2 серии!
                url="https://shikimori.one/animes/202",
            )
        ]

        with patch("app.services.tracker.ShikimoriGraphQLClient") as mock_shiki_cls:
            mock_shiki_inst = MagicMock()
            mock_shiki_inst.__aenter__ = AsyncMock(return_value=mock_shiki_inst)
            mock_shiki_inst.__aexit__ = AsyncMock(return_value=None)
            mock_shiki_inst.fetch_animes_by_ids = AsyncMock(return_value=mock_anime_infos)
            mock_shiki_cls.return_value = mock_shiki_inst

            tracker = TrackerService(
                session=db_session,
                encryption_key="dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ=",
            )
            deltas = await tracker.check_user_updates(user_id=user_id)

            assert len(deltas) == 1
            assert deltas[0].shiki_id == 202
            assert deltas[0].old_episodes_aired == 10
            assert deltas[0].new_episodes_aired == 12
            assert deltas[0].new_episodes_count == 2

            await db_session.refresh(title)
            assert title.last_episodes_aired == 12

    @pytest.mark.asyncio
    async def test_tracker_no_new_episodes(self, db_session: AsyncSession) -> None:
        """Если количество серий не изменилось, дельта пустая."""
        user_id = 5001

        title = TrackedTitle(
            user_id=user_id,
            shiki_id=303,
            title_name_ru="Ван Пис",
            status_in_table="В работе",
            row_index=None,
            last_episodes_aired=1100,
            total_episodes=None,
        )
        db_session.add(title)
        await db_session.commit()

        mock_anime_infos = [
            AnimeInfo(
                id=303,
                name="One Piece",
                russian="Ван Пис",
                status="ongoing",
                episodes=0,
                episodes_aired=1100,  # То же самое число серий
                url="https://shikimori.one/animes/303",
            )
        ]

        with patch("app.services.tracker.ShikimoriGraphQLClient") as mock_shiki_cls:
            mock_shiki_inst = MagicMock()
            mock_shiki_inst.__aenter__ = AsyncMock(return_value=mock_shiki_inst)
            mock_shiki_inst.__aexit__ = AsyncMock(return_value=None)
            mock_shiki_inst.fetch_animes_by_ids = AsyncMock(return_value=mock_anime_infos)
            mock_shiki_cls.return_value = mock_shiki_inst

            tracker = TrackerService(
                session=db_session,
                encryption_key="dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ=",
            )
            deltas = await tracker.check_user_updates(user_id=user_id)

            assert len(deltas) == 0

    @pytest.mark.asyncio
    async def test_tracker_calculates_debts_and_respects_ignore_reminders(
        self, db_session: AsyncSession
    ) -> None:
        """Проверка расчета долгов: отстающие серии фиксируются, если ignore_reminders=False, и игнорируются при ignore_reminders=True."""
        user_id = 5001

        # Тайтл 1: Отстает (залито 2, вышло 4), ignore_reminders=False -> должен быть в долгах
        title_debt = TrackedTitle(
            user_id=user_id,
            shiki_id=401,
            title_name_ru="Тайтл с долгом",
            status_in_table="В работе",
            row_index=None,
            last_episodes_aired=2,
            total_episodes=12,
            ignore_reminders=False,
        )
        # Тайтл 2: Отстает (залито 1, вышло 3), но ignore_reminders=True -> НЕ должен быть в долгах
        title_ignored = TrackedTitle(
            user_id=user_id,
            shiki_id=402,
            title_name_ru="Тайтл в игноре",
            status_in_table="В работе",
            row_index=None,
            last_episodes_aired=1,
            total_episodes=12,
            ignore_reminders=True,
        )
        db_session.add_all([title_debt, title_ignored])
        await db_session.commit()

        mock_anime_infos = [
            AnimeInfo(
                id=401,
                name="Title Debt",
                russian="Тайтл с долгом",
                status="ongoing",
                episodes=12,
                episodes_aired=4,
                url="https://shikimori.one/animes/401",
            ),
            AnimeInfo(
                id=402,
                name="Title Ignored",
                russian="Тайтл в игноре",
                status="ongoing",
                episodes=12,
                episodes_aired=3,
                url="https://shikimori.one/animes/402",
            ),
        ]

        with patch("app.services.tracker.ShikimoriGraphQLClient") as mock_shiki_cls:
            mock_shiki_inst = MagicMock()
            mock_shiki_inst.__aenter__ = AsyncMock(return_value=mock_shiki_inst)
            mock_shiki_inst.__aexit__ = AsyncMock(return_value=None)
            mock_shiki_inst.fetch_animes_by_ids = AsyncMock(return_value=mock_anime_infos)
            mock_shiki_cls.return_value = mock_shiki_inst

            tracker = TrackerService(
                session=db_session,
                encryption_key="dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ=",
            )
            result = await tracker.check_user_updates_full(user_id=user_id)

            # Дельты зафиксированы для обоих тайтлов
            assert len(result.deltas) == 2

            # Долг должен быть только для тайтла 401
            assert len(result.debts) == 1
            assert result.debts[0].shiki_id == 401
            assert result.debts[0].title_name_ru == "Тайтл с долгом"
            assert result.debts[0].uploaded_episodes == 2
            assert result.debts[0].aired_episodes == 4
            assert result.debts[0].missing_episodes_text == "3-4"
