"""Unit-тесты для диалога настроек пользователя и онбординга."""
from __future__ import annotations

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.dialogs.onboarding.dialog import validate_time_format
from app.bot.dialogs.settings.dialog import (
    SettingsSG,
    get_ignored_titles_data,
    get_settings_main_data,
    get_sheets_screen_data,
    on_disconnect_sheets,
    on_restore_reminders,
    on_time_input_error,
    on_time_input_success,
)
from app.bot.dialogs.titles.dialog import get_title_detail_data, on_toggle_reminders
from app.db.models import GoogleCredentials, TrackedTitle, User


class TestSettingsDialog:
    """Тестирование компонентов диалога настроек."""

    @pytest.fixture
    async def db_session(self) -> AsyncSession:
        from app.db.models import Base
        from app.db.session import create_session_factory

        factory = create_session_factory("sqlite+aiosqlite:///:memory:")
        async with factory() as session:
            engine = session.bind
            assert engine is not None
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            yield session

    def test_validate_time_format_valid(self) -> None:
        """Корректные форматы времени проходят валидацию без исключений."""
        assert validate_time_format("09:00") == "09:00"
        assert validate_time_format("00:00") == "00:00"
        assert validate_time_format("23:59") == "23:59"
        assert validate_time_format(" 18:30 ") == "18:30"

    def test_validate_time_format_invalid(self) -> None:
        """Невалидные форматы времени вызывают ValueError."""
        invalid_times = [
            "24:00",
            "12:60",
            "9:00",
            "09:0",
            "abc",
            "12-00",
            "12:00:00",
            "",
            "25:10",
        ]
        for val in invalid_times:
            with pytest.raises(ValueError):
                validate_time_format(val)

    @pytest.mark.asyncio
    async def test_on_time_input_success(self, db_session: AsyncSession) -> None:
        """Успешное сохранение валидного времени в настройках пользователя."""
        user = User(telegram_id=987654, delivery_time=datetime.time(10, 0, 0), timezone="Europe/Moscow")
        db_session.add(user)
        await db_session.commit()

        mock_event = MagicMock()
        mock_event.from_user.id = 987654
        mock_event.answer = AsyncMock()

        mock_manager = MagicMock()
        mock_manager.middleware_data = {"session": db_session}
        mock_manager.switch_to = AsyncMock()

        await on_time_input_success(mock_event, None, mock_manager, "19:45")

        await db_session.refresh(user)
        assert user.delivery_time == datetime.time(19, 45, 0)
        mock_manager.switch_to.assert_called_with(SettingsSG.main)
        assert mock_event.answer.called

    @pytest.mark.asyncio
    async def test_on_time_input_error(self) -> None:
        """Обработчик ошибки валидации времени отправляет предупреждение пользователю."""
        mock_event = MagicMock()
        mock_event.answer = AsyncMock()
        mock_manager = MagicMock()

        await on_time_input_error(mock_event, None, mock_manager, ValueError("err"))
        assert mock_event.answer.called
        assert "Некорректный формат времени" in mock_event.answer.call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_settings_main_data(self, db_session: AsyncSession) -> None:
        """Геттер главного окна настроек возвращает корректную сводку."""
        user = User(telegram_id=111, delivery_time=datetime.time(12, 0, 0))
        title = TrackedTitle(
            user_id=111,
            shiki_id=1001,
            title_name_ru="Тайтл в игноре",
            status_in_table="Запланировано",
            ignore_reminders=True,
        )
        creds = GoogleCredentials(
            user_id=111,
            encrypted_refresh_token="enc_token_123",
            client_id="client_111",
            client_secret="secret_111",
            scopes="https://www.googleapis.com/auth/spreadsheets",
            spreadsheet_id="sheet123",
        )
        db_session.add_all([user, title, creds])
        await db_session.commit()

        mock_manager = MagicMock()
        mock_manager.middleware_data = {"session": db_session}
        mock_user = MagicMock()
        mock_user.id = 111
        mock_manager.event.from_user = mock_user

        data = await get_settings_main_data(mock_manager)
        assert data["delivery_time"] == "12:00"
        assert data["is_sheet_connected"] is True
        assert data["ignored_count"] == 1

    @pytest.mark.asyncio
    async def test_get_sheets_screen_data(self, db_session: AsyncSession) -> None:
        """Геттер Google Таблиц формирует корректные флаги и ссылку на эталонный шаблон."""
        creds = GoogleCredentials(
            user_id=222,
            encrypted_refresh_token="enc_token_222",
            client_id="client_222",
            client_secret="secret_222",
            scopes="https://www.googleapis.com/auth/spreadsheets",
            spreadsheet_id="test_sheet_id",
        )
        db_session.add(creds)
        await db_session.commit()

        mock_manager = MagicMock()
        mock_manager.middleware_data = {"session": db_session}
        mock_user = MagicMock()
        mock_user.id = 222
        mock_manager.event.from_user = mock_user

        data = await get_sheets_screen_data(mock_manager)
        assert data["is_connected"] is True
        assert data["sheet_id"] == "test\\_sheet\\_id"
        assert "1wiDiRPt_zliosdTpC9R-1tREAy1x5h_OnDBQN_sb3Lc" in data["template_url"]

    @pytest.mark.asyncio
    async def test_disconnect_sheets(self, db_session: AsyncSession) -> None:
        """Отключение Google Таблицы очищает spreadsheet_id."""
        creds = GoogleCredentials(
            user_id=555,
            encrypted_refresh_token="enc_token_555",
            client_id="client_555",
            client_secret="secret_555",
            scopes="https://www.googleapis.com/auth/spreadsheets",
            spreadsheet_id="active_sheet",
        )
        db_session.add(creds)
        await db_session.commit()

        mock_event = MagicMock()
        mock_event.from_user.id = 555
        mock_event.answer = AsyncMock()

        mock_manager = MagicMock()
        mock_manager.middleware_data = {"session": db_session}
        mock_manager.switch_to = AsyncMock()

        await on_disconnect_sheets(mock_event, MagicMock(), mock_manager)

        await db_session.refresh(creds)
        assert creds.spreadsheet_id is None
        mock_manager.switch_to.assert_called_with(SettingsSG.main)

    @pytest.mark.asyncio
    async def test_toggle_and_restore_reminders(self, db_session: AsyncSession) -> None:
        """Переключение напоминаний в карточке тайтла и возврат через подменю игнора."""
        title = TrackedTitle(
            user_id=333,
            shiki_id=3003,
            title_name_ru="Экспериментальный тайтл",
            status_in_table="Смотрю",
            ignore_reminders=False,
        )
        db_session.add(title)
        await db_session.commit()
        await db_session.refresh(title)

        # 1. Проверяем get_title_detail_data
        mock_manager = MagicMock()
        mock_manager.middleware_data = {"session": db_session}
        mock_manager.dialog_data = {"selected_title_id": str(title.id)}

        detail_data = await get_title_detail_data(mock_manager)
        assert detail_data["ignore_reminders"] is False
        assert "Не напоминать о долгах" in detail_data["reminders_btn_text"]

        # 2. Переключаем на игнор
        mock_event = MagicMock()
        mock_event.answer = AsyncMock()
        await on_toggle_reminders(mock_event, MagicMock(), mock_manager)

        await db_session.refresh(title)
        assert title.ignore_reminders is True
        assert "отключены" in mock_event.answer.call_args[0][0]

        # 3. Проверяем отображение в get_ignored_titles_data
        mock_user = MagicMock()
        mock_user.id = 333
        mock_manager.event.from_user = mock_user
        ignored_data = await get_ignored_titles_data(mock_manager)
        assert ignored_data["count"] == 1
        assert ignored_data["items"][0]["id"] == str(title.id)

        # 4. Восстанавливаем напоминания через on_restore_reminders
        await on_restore_reminders(mock_event, MagicMock(), mock_manager, str(title.id))
        await db_session.refresh(title)
        assert title.ignore_reminders is False
        assert "возвращен в напоминания" in mock_event.answer.call_args[0][0]
