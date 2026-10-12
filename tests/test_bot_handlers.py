"""Unit-тесты для базовых команд бота (/start, /help, /sync).

Стратегия: TDD Red Phase.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import Chat, Message, User as TelegramUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.common import cmd_help, cmd_start
from app.bot.handlers.manual import cmd_sync
from app.db.models import Base, User
from app.db.session import create_session_factory
from app.services.digest import TitleUpdateDelta


class TestBotHandlers:
    """Тестирование хэндлеров aiogram."""

    @pytest.fixture
    async def db_session(self) -> AsyncSession:
        factory = create_session_factory("sqlite+aiosqlite:///:memory:")
        async with factory() as session:
            engine = session.bind
            assert engine is not None
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            yield session

    def _make_mock_message(self, user_id: int, username: str = "testuser") -> Message:
        msg = MagicMock(spec=Message)
        msg.from_user = MagicMock(spec=TelegramUser)
        msg.from_user.id = user_id
        msg.from_user.username = username
        msg.from_user.first_name = "TestUser"
        msg.chat = MagicMock(spec=Chat)
        msg.chat.id = user_id
        msg.answer = AsyncMock()
        return msg

    @pytest.mark.asyncio
    async def test_cmd_start_creates_user_if_not_exists(
        self, db_session: AsyncSession
    ) -> None:
        msg = self._make_mock_message(user_id=7777, username="newbie")

        await cmd_start(msg, session=db_session)

        # Пользователь создан в БД
        created_user = await db_session.get(User, 7777)
        assert created_user is not None
        assert created_user.username == "newbie"
        assert msg.answer.called
        assert "Добро пожаловать" in msg.answer.call_args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_help(self) -> None:
        msg = self._make_mock_message(user_id=123)

        await cmd_help(msg)

        assert msg.answer.called
        text = msg.answer.call_args[0][0]
        assert "/start" in text
        assert "/sync" in text

    @pytest.mark.asyncio
    async def test_cmd_menu(self) -> None:
        from app.bot.handlers.common import cmd_menu

        msg = self._make_mock_message(user_id=123)
        await cmd_menu(msg)

        assert msg.answer.called
        text = msg.answer.call_args[0][0]
        assert "Главное меню" in text
        reply_markup = msg.answer.call_args[1].get("reply_markup")
        assert reply_markup is not None
        inline_buttons = [btn.text for row in reply_markup.inline_keyboard for btn in row]
        assert "📋 Мои тайтлы" in inline_buttons
        assert "🔄 Синхронизация" in inline_buttons

    @pytest.mark.asyncio
    async def test_cmd_sync_triggers_tracker_and_sends_digest(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BOT_TOKEN", "test:token123")
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
        monkeypatch.setenv("ENCRYPTION_KEY", "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ=")
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "csec")
        monkeypatch.setenv("ADMIN_TELEGRAM_ID", "123456789")

        user = User(telegram_id=8888, username="sync_user")
        db_session.add(user)
        await db_session.commit()

        msg = self._make_mock_message(user_id=8888)

        mock_deltas = [
            TitleUpdateDelta(
                title_name_ru="Тестовый тайтл",
                shiki_id=1,
                old_episodes_aired=0,
                new_episodes_aired=1,
                total_episodes=12,
                shikimori_url="https://shikimori.one/animes/1",
            )
        ]

        from app.services.digest import DigestResult

        mock_result = DigestResult(deltas=mock_deltas, debts=[])

        with patch("app.bot.handlers.manual.TrackerService") as mock_tracker_cls:
            mock_tracker_inst = MagicMock()
            mock_tracker_inst.check_user_updates = AsyncMock(return_value=mock_deltas)
            mock_tracker_inst.check_user_updates_full = AsyncMock(return_value=mock_result)
            mock_tracker_cls.return_value = mock_tracker_inst

            await cmd_sync(msg, session=db_session)

            assert msg.answer.call_count >= 1
            # Сообщение с результатом содержит имя тайтла
            last_text = msg.answer.call_args_list[-1][0][0]
            assert "Тестовый тайтл" in last_text

    @pytest.mark.asyncio
    async def test_persistent_reply_keyboard_structure(self) -> None:
        """Проверка структуры и свойств постоянной клавиатуры."""
        from app.bot.keyboards import get_persistent_main_keyboard

        kb = get_persistent_main_keyboard()
        assert kb.is_persistent is True
        assert kb.resize_keyboard is True
        button_texts = [btn.text for row in kb.keyboard for btn in row]
        assert "🏠 Главное меню" in button_texts
        assert "📋 Мой список" in button_texts
        assert "⚙️ Настройки" in button_texts

    @pytest.mark.asyncio
    async def test_nav_handlers(self) -> None:
        """Проверка вызова диалогов и меню из кнопок Reply-клавиатуры."""
        from app.bot.handlers.common import nav_main_menu, nav_my_titles, nav_settings
        from app.bot.dialogs.titles.dialog import TitlesSG
        from app.bot.dialogs.onboarding.dialog import OnboardingSG
        from aiogram_dialog import StartMode

        msg = self._make_mock_message(user_id=123)
        mock_dialog_manager = MagicMock()
        mock_dialog_manager.start = AsyncMock()

        # 1. 🏠 Главное меню
        await nav_main_menu(msg)
        assert msg.answer.called
        assert "Главное меню" in msg.answer.call_args[0][0]

        # 2. 📋 Мой список
        await nav_my_titles(msg, dialog_manager=mock_dialog_manager)
        mock_dialog_manager.start.assert_called_with(
            TitlesSG.list_titles, mode=StartMode.RESET_STACK
        )

        # 3. ⚙️ Настройки
        from app.bot.dialogs.settings.dialog import SettingsSG

        await nav_settings(msg, dialog_manager=mock_dialog_manager)
        mock_dialog_manager.start.assert_called_with(
            SettingsSG.main, mode=StartMode.RESET_STACK
        )

    @pytest.mark.asyncio
    async def test_fallback_unknown_message(self) -> None:
        """Фоллбэк на неизвестное сообщение отправляет подсказку и постоянную клавиатуру."""
        from app.bot.handlers.common import fallback_unknown_message

        msg = self._make_mock_message(user_id=123)
        msg.text = "случайный неизвестный текст"

        await fallback_unknown_message(msg)

        assert msg.answer.called
        text = msg.answer.call_args[0][0]
        assert "Я не понял это сообщение" in text
        reply_markup = msg.answer.call_args[1].get("reply_markup")
        assert reply_markup is not None
        assert reply_markup.is_persistent is True
