"""Unit-тесты для взаимодействия с многостраничной командной Google Таблицей."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from cryptography.fernet import Fernet
import pytest

from app.clients.google_sheets import GoogleSheetsClient


class TestTeamSpreadsheet:
    """Тестирование работы с командной таблицей."""

    @pytest.fixture
    def sheets_client(self) -> GoogleSheetsClient:
        return GoogleSheetsClient(
            client_id="mock_client_id",
            client_secret="mock_client_secret",
            encrypted_refresh_token="mock_enc_token",
            encryption_key=Fernet.generate_key().decode(),
        )

    def test_col_idx_to_letter(self) -> None:
        """Проверка конвертации индексов колонок в буквы."""
        assert GoogleSheetsClient.col_idx_to_letter(0) == "A"
        assert GoogleSheetsClient.col_idx_to_letter(1) == "B"
        assert GoogleSheetsClient.col_idx_to_letter(2) == "C"
        assert GoogleSheetsClient.col_idx_to_letter(3) == "D"
        assert GoogleSheetsClient.col_idx_to_letter(25) == "Z"
        assert GoogleSheetsClient.col_idx_to_letter(26) == "AA"

    @pytest.mark.asyncio
    async def test_get_workable_sheets_excludes_first_and_last(
        self, sheets_client: GoogleSheetsClient
    ) -> None:
        """Проверка исключения первой и последней вкладок таблицы."""
        mock_meta = {
            "sheets": [
                {"properties": {"title": "Правила (первая)"}},
                {"properties": {"title": "Осень 2026"}},
                {"properties": {"title": "Лето 2026"}},
                {"properties": {"title": "Архив (последняя)"}},
            ]
        }

        with patch.object(sheets_client, "_build_service") as mock_build:
            mock_service = MagicMock()
            mock_service.spreadsheets().get().execute.return_value = mock_meta
            mock_build.return_value = mock_service

            sheets = await sheets_client.get_workable_sheets("spreadsheet_id")
            assert sheets == ["Осень 2026", "Лето 2026"]

    @pytest.mark.asyncio
    async def test_find_and_update_team_subtitles_success(
        self, sheets_client: GoogleSheetsClient
    ) -> None:
        """Поиск тайтла, определение колонок серий и чекбокса, выставление серии и галочки первых сабов."""
        mock_meta = {
            "sheets": [
                {"properties": {"title": "Титульный"}},
                {"properties": {"title": "Онгоинги"}},
                {"properties": {"title": "Служебный"}},
            ]
        }

        # Таблица: Колонка A - Название, B - Ссылка, C - Сабы (номер), D - Subs (чекбокс)
        sheet_values = [
            ["Тайтл", "Shikimori", "Сабы", "Subs"],
            ["Магическая битва", "https://shikimori.one/animes/40748", "2", "FALSE"],
        ]

        with patch.object(sheets_client, "_build_service") as mock_build:
            mock_service = MagicMock()
            mock_service.spreadsheets().get().execute.return_value = mock_meta
            mock_service.spreadsheets().values().get().execute.return_value = {"values": sheet_values}
            mock_service.spreadsheets().values().batchUpdate().execute.return_value = {"totalUpdatedCells": 2}
            mock_build.return_value = mock_service

            updated = await sheets_client.find_and_update_team_subtitles(
                spreadsheet_id="team_sheet_id",
                shiki_id=40748,
                episode_num=3,
            )

            assert updated is True
            # Проверяем отправленные данные в batchUpdate
            batch_call = mock_service.spreadsheets().values().batchUpdate.call_args[1]
            body = batch_call["body"]
            data = body["data"]

            # 2 обновления: колонка C (серия = 3) и колонка D (чекбокс = True)
            assert len(data) == 2
            ranges = [d["range"] for d in data]
            assert "'Онгоинги'!C2" in ranges
            assert "'Онгоинги'!D2" in ranges
            assert data[0]["values"] == [[3]]
            assert data[1]["values"] == [[True]]

    @pytest.mark.asyncio
    async def test_find_and_update_team_subtitles_preserves_checked_box(
        self, sheets_client: GoogleSheetsClient
    ) -> None:
        """Если чекбокс первых сабов уже был TRUE, повторно он не перезаписывается."""
        mock_meta = {
            "sheets": [
                {"properties": {"title": "Инфо"}},
                {"properties": {"title": "Релизы"}},
                {"properties": {"title": "Конец"}},
            ]
        }

        sheet_values = [
            ["Тайтл", "Shikimori", "Subs status", "Subs"],
            ["Блич", "40748", "5", "TRUE"],  # Чекбокс уже TRUE!
        ]

        with patch.object(sheets_client, "_build_service") as mock_build:
            mock_service = MagicMock()
            mock_service.spreadsheets().get().execute.return_value = mock_meta
            mock_service.spreadsheets().values().get().execute.return_value = {"values": sheet_values}
            mock_service.spreadsheets().values().batchUpdate().execute.return_value = {"totalUpdatedCells": 1}
            mock_build.return_value = mock_service

            updated = await sheets_client.find_and_update_team_subtitles(
                spreadsheet_id="team_sheet_id",
                shiki_id=40748,
                episode_num=6,
            )

            assert updated is True
            batch_call = mock_service.spreadsheets().values().batchUpdate.call_args[1]
            data = batch_call["body"]["data"]

            # Обновляется только колонка серий C2, а D2 (чекбокс) не трогается
            assert len(data) == 1
            assert data[0]["range"] == "'Релизы'!C2"
            assert data[0]["values"] == [[6]]
