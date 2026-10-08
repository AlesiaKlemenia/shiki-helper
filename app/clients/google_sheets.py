"""Клиент Google Sheets API v4 и Google OAuth 2.0 flow.

Особенности:
- Генерация ссылки авторизации Google OAuth (scope spreadsheets).
- Обмен authorization code на refresh_token и его безопасное шифрование через TokenEncryptor.
- Пакетное чтение диапазона A2:D с отсеиванием завершенных/прочих тайтлов (только «В работе», «В планах», «Анонс»).
- Пакетное обновление (batchUpdate) ячеек колонки D с форматированием {aired}/{total or '?'}.
- Отслеживание отозванных токенов (GoogleTokenRevokedError при invalid_grant).
- Все синхронные вызовы Google API оборачиваются в asyncio.to_thread.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow  # type: ignore[import-untyped]
from googleapiclient.discovery import build  # type: ignore[import-untyped]

from app.core.security import TokenEncryptor

logger = logging.getLogger(__name__)

SCOPES: list[str] = ["https://www.googleapis.com/auth/spreadsheets"]
REDIRECT_URI: str = "urn:ietf:wg:oauth:2.0:oob"
ALLOWED_STATUSES: set[str] = {"В работе", "В планах", "Анонс"}
_ALLOWED_STATUSES_LOWER: set[str] = {s.lower() for s in ALLOWED_STATUSES}


def is_status_allowed(status: str) -> bool:
    """Проверяет, входит ли статус релиза в число отслеживаемых."""
    return status.strip().lower() in _ALLOWED_STATUSES_LOWER



class GoogleTokenRevokedError(Exception):
    """Исключение, сигнализирующее об отзыве или недействительности Google OAuth токена."""

    pass


def format_episodes_cell(aired: int, total: Optional[int]) -> str:
    """Форматирует строку для колонки D таблицы: {aired}/{total or '?'}.

    Примеры:
        format_episodes_cell(5, 12) -> "5/12"
        format_episodes_cell(10, None) -> "10/?"
        format_episodes_cell(0, 0) -> "0/?"
    """
    total_str = str(total) if total and total > 0 else "?"
    return f"{aired}/{total_str}"


@dataclass(frozen=True, slots=True)
class SheetRow:
    """Строка таблицы Google Sheets в диапазоне A2:D."""

    row_index: int
    title_name_ru: str
    shiki_link_or_id: str
    status: str
    current_episodes_text: str = ""

    def extract_shiki_id(self) -> Optional[int]:
        """Извлекает числовой ID Shikimori из ссылки или сырого значения колонки B.

        Примеры:
            "https://shikimori.one/animes/40748" -> 40748
            "https://shikimori.one/animes/z40748-jujutsu-kaisen" -> 40748
            "40748" -> 40748
            "invalid" -> None
        """
        raw = self.shiki_link_or_id.strip()
        if not raw:
            return None

        # Проверка на числовой ID напрямую
        if raw.isdigit():
            return int(raw)

        # Регулярка для извлечения ID из различных форматов URL Shikimori
        match = re.search(r"/animes/(?:z|a)?(\d+)", raw)
        if match:
            return int(match.group(1))

        return None


class GoogleOAuthHelper:
    """Хелпер для прохождения Google OAuth 2.0 flow."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        encryption_key: str,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.encryptor = TokenEncryptor(encryption_key)

    def _create_flow(self) -> Flow:
        """Создает экземпляр google_auth_oauthlib Flow."""
        client_config = {
            "installed": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
            }
        }
        flow = Flow.from_client_config(
            client_config=client_config,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI,
        )
        return flow

    def get_authorization_url(self) -> str:
        """Генерирует URL для перехода пользователя на страницу подтверждения прав в Google."""
        flow = self._create_flow()
        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        return str(authorization_url)

    def exchange_code_for_encrypted_token(self, auth_code: str) -> str:
        """Обменивает authorization code на refresh_token и шифрует его через Fernet.

        Args:
            auth_code: Одноразовый код авторизации из Google.

        Returns:
            Зашифрованная строка refresh_token.

        Raises:
            ValueError: Если Google не вернул refresh_token.
        """
        flow = self._create_flow()
        flow.fetch_token(code=auth_code.strip())

        credentials = flow.credentials
        refresh_token = credentials.refresh_token

        if not refresh_token:
            raise ValueError(
                "Google не вернул refresh_token. "
                "Убедитесь, что передан параметр prompt=consent."
            )

        return self.encryptor.encrypt(refresh_token)


class GoogleSheetsClient:
    """Асинхронный клиент для взаимодействия с Google Sheets API."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        encrypted_refresh_token: str,
        encryption_key: str,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.encryptor = TokenEncryptor(encryption_key)
        self.encrypted_refresh_token = encrypted_refresh_token

    def _build_service(self) -> Any:
        """Создает и аутентифицирует синхронный сервис Google Sheets API v4."""
        decrypted_refresh_token = self.encryptor.decrypt(self.encrypted_refresh_token)
        if not decrypted_refresh_token:
            raise GoogleTokenRevokedError("Не удалось расшифровать refresh_token.")

        credentials = Credentials(
            token=None,
            refresh_token=decrypted_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=SCOPES,
        )

        return build("sheets", "v4", credentials=credentials, cache_discovery=False)

    async def read_releases_range(self, spreadsheet_id: str) -> list[SheetRow]:
        """Асинхронно считывает диапазон A2:D и фильтрует по актуальным статусам.

        Args:
            spreadsheet_id: ID Google Таблицы.

        Returns:
            Список отфильтрованных строк SheetRow.

        Raises:
            GoogleTokenRevokedError: Если токен пользователя отозван или недействителен.
        """

        def _sync_read() -> list[SheetRow]:
            try:
                service = self._build_service()
                result = (
                    service.spreadsheets()
                    .values()
                    .get(spreadsheetId=spreadsheet_id, range="A2:D")
                    .execute()
                )
            except RefreshError as exc:
                logger.error("Ошибка обновления Google OAuth токена: %s", exc)
                raise GoogleTokenRevokedError(
                    "Токен Google OAuth отозван или устарел. Требуется повторная авторизация."
                ) from exc

            raw_values = result.get("values", [])
            valid_rows: list[SheetRow] = []

            for idx, row in enumerate(raw_values, start=2):
                if not row or len(row) < 3:
                    continue

                title_ru = str(row[0]).strip()
                shiki_link = str(row[1]).strip()
                status = str(row[2]).strip()
                episodes_text = str(row[3]).strip() if len(row) > 3 else ""

                if not title_ru or not status:
                    continue

                # Фильтрация по статусу (регистронезависимо)
                if not is_status_allowed(status):
                    continue

                valid_rows.append(
                    SheetRow(
                        row_index=idx,
                        title_name_ru=title_ru,
                        shiki_link_or_id=shiki_link,
                        status=status,
                        current_episodes_text=episodes_text,
                    )
                )

            return valid_rows

        return await asyncio.to_thread(_sync_read)

    async def batch_update_episodes(
        self,
        spreadsheet_id: str,
        updates: list[tuple[int, str]],
    ) -> int:
        """Пакетно обновляет значения в колонке D таблицы для экономии квот API.

        Args:
            spreadsheet_id: ID Google Таблицы.
            updates: Список кортежей (row_index, formatted_value), например [(2, "5/12")].

        Returns:
            Количество успешно обновленных ячеек.
        """
        if not updates:
            return 0

        def _sync_batch_update() -> int:
            service = self._build_service()

            data_payload = [
                {
                    "range": f"D{row_idx}",
                    "values": [[val]],
                }
                for row_idx, val in updates
            ]

            body = {
                "valueInputOption": "USER_ENTERED",
                "data": data_payload,
            }

            try:
                response = (
                    service.spreadsheets()
                    .values()
                    .batchUpdate(spreadsheetId=spreadsheet_id, body=body)
                    .execute()
                )
                updated_cells = int(response.get("totalUpdatedCells", len(updates)))
                return updated_cells
            except RefreshError as exc:
                logger.error("Ошибка обновления Google OAuth токена: %s", exc)
                raise GoogleTokenRevokedError(
                    "Токен Google OAuth отозван или устарел."
                ) from exc

        return await asyncio.to_thread(_sync_batch_update)
