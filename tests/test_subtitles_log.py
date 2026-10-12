"""Unit-тесты для парсера логов субтитров и хэндлера обработки заливок."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import Chat, Message, User as TelegramUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.subtitles import handle_subtitles_log_message
from app.db.models import Base, GoogleCredentials, TrackedTitle, User
from app.db.session import create_session_factory
from app.services.subtitles_log import SubtitlesLogParser


class TestSubtitlesLogParser:
    """Тестирование SubtitlesLogParser."""

    def test_is_subtitles_log_filter(self) -> None:
        """Сообщение распознается только при строгом наличии маркера 'Тип субтитров: subtitles'."""
        valid_texts = [
            "Тип субтитров: subtitles\nПуть: 40748/3/sub.ass",
            "тип субтитров: subtitles\nСерия: 5",
            "  ТИП СУБТИТРОВ: SUBTITLES  \nID: 100",
        ]
        for t in valid_texts:
            assert SubtitlesLogParser.is_subtitles_log(t) is True

        invalid_texts = [
            "Тип субтитров: dubbing\nПуть: 40748/3/audio.mp3",
            "Субтитры залиты успешно",
            "Привет, как дела?",
            "",
            None,
        ]
        for t in invalid_texts:
            assert SubtitlesLogParser.is_subtitles_log(t) is False

    def test_parse_from_path(self) -> None:
        """Извлечение shiki_id и номера серии напрямую из пути 'Путь: <id>/<ep>/...'."""
        log_text = (
            "Готово!\n"
            "Тип субтитров: subtitles\n"
            "Путь: 40748/5/subtitles.ass\n"
            "Размер: 150KB"
        )
        payload = SubtitlesLogParser.parse(log_text)
        assert payload is not None
        assert payload.shiki_id == 40748
        assert payload.episode_num == 5

    def test_parse_from_explicit_fields_and_url(self) -> None:
        """Извлечение параметров из ссылки Shikimori и поля 'Серия: N'."""
        log_text = (
            "Тип субтитров: subtitles\n"
            "Ссылка: https://shikimori.one/animes/z5114-fullmetal-alchemist-brotherhood\n"
            "Серия: 14"
        )
        payload = SubtitlesLogParser.parse(log_text)
        assert payload is not None
        assert payload.shiki_id == 5114
        assert payload.episode_num == 14

    def test_parse_missing_fields_returns_none(self) -> None:
        """Если нет номера серии или ID, парсер возвращает None."""
        log_without_ep = (
            "Тип субтитров: subtitles\n"
            "Shikimori ID: 40748\n"
            "Статус: OK"
        )
        assert SubtitlesLogParser.parse(log_without_ep) is None

        log_without_id = (
            "Тип субтитров: subtitles\n"
            "Серия: 3"
        )
        assert SubtitlesLogParser.parse(log_without_id) is None


class TestSubtitlesHandler:
    """Тестирование хэндлера handle_subtitles_log_message."""

    @pytest.fixture
    async def db_session(self) -> AsyncSession:
        factory = create_session_factory("sqlite+aiosqlite:///:memory:")
        async with factory() as session:
            engine = session.bind
            assert engine is not None
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            user = User(telegram_id=9001, timezone="Europe/Moscow")
            session.add(user)
            await session.commit()
            yield session

    def _make_mock_message(self, user_id: int, text: str) -> Message:
        msg = MagicMock(spec=Message)
        msg.from_user = MagicMock(spec=TelegramUser)
        msg.from_user.id = user_id
        msg.chat = MagicMock(spec=Chat)
        msg.chat.id = user_id
        msg.text = text
        msg.answer = AsyncMock()
        return msg

    @pytest.mark.asyncio
    async def test_subtitles_log_updates_status_and_episodes(
        self, db_session: AsyncSession
    ) -> None:
        """Лог сабов переводит тайтл из 'Анонс' в 'В работе' и обновляет серию."""
        user_id = 9001
        title = TrackedTitle(
            user_id=user_id,
            shiki_id=777,
            title_name_ru="Тестовый релиз",
            status_in_table="Анонс",
            row_index=3,
            last_episodes_aired=0,
            total_episodes=12,
        )
        creds = GoogleCredentials(
            user_id=user_id,
            encrypted_refresh_token="enc_token",
            client_id="cid",
            client_secret="csec",
            scopes="https://www.googleapis.com/auth/spreadsheets",
            spreadsheet_id="test_sheet",
        )
        db_session.add_all([title, creds])
        await db_session.commit()

        log_text = (
            "Тип субтитров: subtitles\n"
            "Путь: 777/1/sub.ass"
        )
        msg = self._make_mock_message(user_id=user_id, text=log_text)

        with patch("app.bot.handlers.subtitles.GoogleSheetsClient") as mock_sheets_cls:
            mock_sheets_inst = MagicMock()
            mock_sheets_inst.update_title_row = AsyncMock()
            mock_sheets_cls.return_value = mock_sheets_inst

            await handle_subtitles_log_message(msg, session=db_session)

            # Проверяем обновление БД
            await db_session.refresh(title)
            assert title.status_in_table == "В работе"
            assert title.last_episodes_aired == 1

            # Проверяем вызов обновления Google Таблицы
            mock_sheets_inst.update_title_row.assert_awaited_once_with(
                spreadsheet_id="test_sheet",
                row_index=3,
                status="В работе",
                episodes_text="1/12",
            )

            # Проверяем ответ бота
            assert msg.answer.called
            answer_text = msg.answer.call_args[0][0]
            assert "Лог сабов успешно обработан" in answer_text
            assert "Тестовый релиз" in answer_text
            assert "В работе" in answer_text

    @pytest.mark.asyncio
    async def test_subtitles_log_title_not_found(
        self, db_session: AsyncSession
    ) -> None:
        """Если тайтл с данным ID не отслеживается, отправляется информационное сообщение."""
        user_id = 9001
        log_text = (
            "Тип субтитров: subtitles\n"
            "Путь: 99999/2/sub.ass"
        )
        msg = self._make_mock_message(user_id=user_id, text=log_text)

        await handle_subtitles_log_message(msg, session=db_session)

        assert msg.answer.called
        answer_text = msg.answer.call_args[0][0]
        assert "не найден в вашем списке" in answer_text
