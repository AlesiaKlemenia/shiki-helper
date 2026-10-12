"""Тесты для обработчиков ошибок (UnknownIntent)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, ErrorEvent, Message, Update
from aiogram_dialog.api.exceptions import UnknownIntent

from app.bot.handlers.errors import handle_unknown_intent


class TestErrorHandlers:
    """Тестирование перехвата ошибок диалогов."""

    @pytest.mark.asyncio
    async def test_handle_unknown_intent_callback_query(self) -> None:
        """При UnknownIntent с callback_query сбрасывается FSM и отправляется меню."""
        mock_state = MagicMock(spec=FSMContext)
        mock_state.clear = AsyncMock()

        mock_cb = MagicMock(spec=CallbackQuery)
        mock_cb.answer = AsyncMock()

        mock_msg = MagicMock(spec=Message)
        mock_msg.answer = AsyncMock()
        mock_cb.message = mock_msg

        mock_update = MagicMock(spec=Update)
        mock_update.callback_query = mock_cb
        mock_update.message = None

        error_event = ErrorEvent(
            update=mock_update,
            exception=UnknownIntent("Test unknown intent"),
        )

        await handle_unknown_intent(error_event, state=mock_state)

        # 1. Сброс FSM
        mock_state.clear.assert_called_once()
        # 2. Квитирование callback query
        mock_cb.answer.assert_called_once()
        # 3. Отправка актуального главного меню
        assert mock_msg.answer.called
        text = mock_msg.answer.call_args[0][0]
        assert "Главное меню" in text
        assert "Сессия предыдущего диалога завершена" in text
        reply_markup = mock_msg.answer.call_args[1].get("reply_markup")
        assert reply_markup is not None

    @pytest.mark.asyncio
    async def test_handle_unknown_intent_message(self) -> None:
        """При UnknownIntent с message сбрасывается FSM и отправляется меню."""
        mock_state = MagicMock(spec=FSMContext)
        mock_state.clear = AsyncMock()

        mock_msg = MagicMock(spec=Message)
        mock_msg.answer = AsyncMock()

        mock_update = MagicMock(spec=Update)
        mock_update.callback_query = None
        mock_update.message = mock_msg

        error_event = ErrorEvent(
            update=mock_update,
            exception=UnknownIntent("Test unknown intent"),
        )

        await handle_unknown_intent(error_event, state=mock_state)

        mock_state.clear.assert_called_once()
        assert mock_msg.answer.called
        text = mock_msg.answer.call_args[0][0]
        assert "Главное меню" in text
