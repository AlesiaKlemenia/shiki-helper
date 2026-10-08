"""Unit-тесты для app/clients/google_sheets.py — Google OAuth flow и Google Sheets API.

Стратегия: TDD Red Phase — тесты написаны ДО реализации.
Используется unittest.mock для изоляции внешних вызовов Google API Client.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from cryptography.fernet import Fernet
import pytest
from google.auth.exceptions import RefreshError

from app.clients.google_sheets import (
    ALLOWED_STATUSES,
    GoogleOAuthHelper,
    GoogleSheetsClient,
    GoogleTokenRevokedError,
    SheetRow,
    format_episodes_cell,
)

TEST_ENCRYPTION_KEY: str = Fernet.generate_key().decode()



class TestSheetRowAndHelpers:
    """Тестирование структуры SheetRow и вспомогательных функций."""

    def test_format_episodes_cell_with_known_total(self) -> None:
        assert format_episodes_cell(aired=5, total=12) == "5/12"

    def test_format_episodes_cell_with_unknown_total(self) -> None:
        assert format_episodes_cell(aired=10, total=None) == "10/?"
        assert format_episodes_cell(aired=0, total=0) == "0/?"

    def test_allowed_statuses_filter(self) -> None:
        assert "В работе" in ALLOWED_STATUSES
        assert "В планах" in ALLOWED_STATUSES
        assert "Анонс" in ALLOWED_STATUSES
        assert "Завершен" not in ALLOWED_STATUSES
        assert "Брошено" not in ALLOWED_STATUSES

    def test_sheet_row_instantiation(self) -> None:
        row = SheetRow(
            row_index=2,
            title_name_ru="Магическая битва",
            shiki_link_or_id="https://shikimori.one/animes/40748",
            status="В работе",
            current_episodes_text="12/24",
        )
        assert row.row_index == 2
        assert row.title_name_ru == "Магическая битва"
        assert row.extract_shiki_id() == 40748

    def test_sheet_row_extract_shiki_id_from_raw_id(self) -> None:
        row = SheetRow(
            row_index=3,
            title_name_ru="Атака титанов",
            shiki_link_or_id="16498",
            status="Анонс",
            current_episodes_text="0/?",
        )
        assert row.extract_shiki_id() == 16498

    def test_sheet_row_extract_shiki_id_invalid(self) -> None:
        row = SheetRow(
            row_index=4,
            title_name_ru="Неизвестно",
            shiki_link_or_id="invalid-link",
            status="В планах",
            current_episodes_text="",
        )
        assert row.extract_shiki_id() is None


class TestGoogleOAuthHelper:
    """Тестирование генерации OAuth URL и обмена кода на зашифрованные токены."""

    def test_get_authorization_url(self) -> None:
        helper = GoogleOAuthHelper(
            client_id="test_client_id.apps.googleusercontent.com",
            client_secret="test_client_secret",
            encryption_key=TEST_ENCRYPTION_KEY,
        )
        url = helper.get_authorization_url()
        assert "accounts.google.com" in url
        assert "test_client_id" in url
        assert "spreadsheets" in url

    @patch("google_auth_oauthlib.flow.Flow.fetch_token")
    def test_exchange_code_success(self, mock_fetch_token: MagicMock) -> None:
        helper = GoogleOAuthHelper(
            client_id="test_client_id",
            client_secret="test_client_secret",
            encryption_key=TEST_ENCRYPTION_KEY,
        )
        mock_credentials = MagicMock()
        mock_credentials.refresh_token = "google_refresh_token_xyz"
        mock_credentials.scopes = ["https://www.googleapis.com/auth/spreadsheets"]

        with patch.object(helper, "_create_flow") as mock_flow_factory:
            mock_flow = MagicMock()
            mock_flow.credentials = mock_credentials
            mock_flow_factory.return_value = mock_flow

            encrypted_token = helper.exchange_code_for_encrypted_token("auth_code_123")

            assert isinstance(encrypted_token, str)
            assert encrypted_token != "google_refresh_token_xyz"
            # Расшифровка должна вернуть оригинальный токен
            decrypted = helper.encryptor.decrypt(encrypted_token)
            assert decrypted == "google_refresh_token_xyz"


class TestGoogleSheetsClient:
    """Тестирование чтения и пакетного обновления диапазона A2:D Google Таблицы."""

    @pytest.mark.asyncio
    async def test_read_releases_range_filters_statuses(self) -> None:
        client = GoogleSheetsClient(
            client_id="cid",
            client_secret="csec",
            encrypted_refresh_token="enc_token",
            encryption_key=TEST_ENCRYPTION_KEY,
        )

        mock_rows = [
            ["Тайтл 1", "https://shikimori.one/animes/101", "В работе", "1/12"],
            ["Тайтл 2", "https://shikimori.one/animes/102", "Завершен", "24/24"],  # Должен быть отфильтрован
            ["Тайтл 3", "103", "В планах", "0/?"],
            ["Тайтл 4", "", "", ""],  # Пустая строка -> отфильтрована
            ["Тайтл 5", "105", "Анонс"],  # Колонки D нет -> default ""
        ]

        mock_service = MagicMock()
        mock_service.spreadsheets().values().get().execute.return_value = {
            "values": mock_rows
        }

        with patch.object(client, "_build_service", return_value=mock_service):
            rows = await client.read_releases_range(spreadsheet_id="test_sheet_id")

            assert len(rows) == 3
            assert rows[0].row_index == 2
            assert rows[0].title_name_ru == "Тайтл 1"
            assert rows[0].status == "В работе"

            assert rows[1].row_index == 4  # 3-я строка в mock была отфильтрована
            assert rows[1].title_name_ru == "Тайтл 3"

            assert rows[2].row_index == 6
            assert rows[2].title_name_ru == "Тайтл 5"

    @pytest.mark.asyncio
    async def test_batch_update_episodes(self) -> None:
        client = GoogleSheetsClient(
            client_id="cid",
            client_secret="csec",
            encrypted_refresh_token="enc_token",
            encryption_key=TEST_ENCRYPTION_KEY,
        )

        updates = [(2, "5/12"), (5, "13/24")]

        mock_service = MagicMock()
        mock_batch_update = mock_service.spreadsheets().values().batchUpdate()
        mock_batch_update.execute.return_value = {"totalUpdatedCells": 2}

        with patch.object(client, "_build_service", return_value=mock_service):
            updated_count = await client.batch_update_episodes(
                spreadsheet_id="test_sheet_id",
                updates=updates,
            )

            assert updated_count == 2

    @pytest.mark.asyncio
    async def test_raises_google_token_revoked_error_on_refresh_error(self) -> None:
        client = GoogleSheetsClient(
            client_id="cid",
            client_secret="csec",
            encrypted_refresh_token="enc_token",
            encryption_key=TEST_ENCRYPTION_KEY,
        )

        mock_service = MagicMock()
        mock_service.spreadsheets().values().get().execute.side_effect = RefreshError(
            "invalid_grant: Token has been expired or revoked."
        )

        with patch.object(client, "_build_service", return_value=mock_service):
            with pytest.raises(GoogleTokenRevokedError, match="Токен Google OAuth отозван"):
                await client.read_releases_range(spreadsheet_id="test_sheet_id")
