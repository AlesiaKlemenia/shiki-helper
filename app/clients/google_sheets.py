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

    def extract_uploaded_episodes(self) -> int:
        """Извлекает количество залитых серий из текста ячейки (например, '5/12', '5/?', '5').

        Примеры:
            '5/12' -> 5
            '10/?' -> 10
            ' 3 '  -> 3
            ''     -> 0
            '?'    -> 0
        """
        raw = self.current_episodes_text.strip()
        if not raw:
            return 0

        # Ищем первое число перед слэшем или строку целиком
        match = re.match(r"^(\d+)", raw)
        if match:
            return int(match.group(1))
        return 0


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
                if not row or len(row) < 2:
                    continue

                title_ru = str(row[0]).strip()
                shiki_link = str(row[1]).strip()
                status = str(row[2]).strip() if len(row) > 2 and row[2] else "В работе"
                episodes_text = str(row[3]).strip() if len(row) > 3 and row[3] else ""

                if not title_ru or not shiki_link:
                    continue

                # Фильтрация по статусу (если указан статус, проверяем допустимость)
                if status and not is_status_allowed(status):
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

    async def update_title_row(
        self,
        spreadsheet_id: str,
        row_index: int,
        status: Optional[str] = None,
        episodes_text: Optional[str] = None,
    ) -> None:
        """Обновляет статус (колонка C) и/или серии (колонка D) для конкретной строки тайтла.

        Args:
            spreadsheet_id: ID Google Таблицы.
            row_index: Номер строки (1-based, например 5).
            status: Новый статус релиза (например 'В работе').
            episodes_text: Отформатированное значение серий (например '3/12').
        """
        updates_payload: list[dict[str, Any]] = []
        if status is not None:
            updates_payload.append({
                "range": f"C{row_index}",
                "values": [[status]],
            })
        if episodes_text is not None:
            updates_payload.append({
                "range": f"D{row_index}",
                "values": [[episodes_text]],
            })

        if not updates_payload:
            return

        def _sync_update() -> None:
            service = self._build_service()
            body = {
                "valueInputOption": "USER_ENTERED",
                "data": updates_payload,
            }
            try:
                service.spreadsheets().values().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body=body,
                ).execute()
            except RefreshError as exc:
                logger.error("Ошибка обновления токена Google OAuth: %s", exc)
                raise GoogleTokenRevokedError(
                    "Токен Google OAuth отозван или устарел."
                ) from exc

        await asyncio.to_thread(_sync_update)

    @staticmethod
    def col_idx_to_letter(idx: int) -> str:
        """Конвертирует 0-based индекс колонки в буквы Excel (0 -> A, 1 -> B, 26 -> AA)."""
        result = []
        idx += 1
        while idx > 0:
            idx, rem = divmod(idx - 1, 26)
            result.append(chr(65 + rem))
        return "".join(reversed(result))

    async def get_workable_sheets(self, spreadsheet_id: str) -> list[str]:
        """Возвращает список рабочих листов таблицы, исключая первый и последний."""

        def _sync_get_sheets() -> list[str]:
            service = self._build_service()
            meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            sheets = meta.get("sheets", [])
            sheet_titles = [s["properties"]["title"] for s in sheets if "properties" in s and "title" in s["properties"]]
            if len(sheet_titles) <= 2:
                return []
            # Исключаем первый и последний листы
            return sheet_titles[1:-1]

        return await asyncio.to_thread(_sync_get_sheets)

    async def find_and_update_team_subtitles(
        self,
        spreadsheet_id: str,
        shiki_id: int,
        episode_num: int,
    ) -> bool:
        """Ищет тайтл по рабочим вкладкам командной таблицы и обновляет серию/чекбокс первых сабов.

        Логика:
        1. Получить рабочие вкладки (без первой и последней).
        2. В каждой вкладке считать строки.
        3. Найти колонку ссылок на Shikimori и строку с целевым shiki_id.
        4. Найти колонку серий ('Subs status', 'Сабы', или числовой 'Subs') и чекбокса ('Subs' булевый).
        5. Обновить номер серии на episode_num.
        6. Если чекбокс первых сабов был False/пустой -> установить True.

        Returns:
            True, если тайтл найден и обновлен в таблице команды, иначе False.
        """

        def _sync_find_and_update() -> bool:
            service = self._build_service()
            meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            sheets = meta.get("sheets", [])
            sheet_titles = [s["properties"]["title"] for s in sheets if "properties" in s and "title" in s["properties"]]
            if len(sheet_titles) <= 2:
                return False

            workable_titles = sheet_titles[1:-1]

            for sheet_name in workable_titles:
                # Читаем лист целиком
                resp = (
                    service.spreadsheets()
                    .values()
                    .get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!A1:Z100")
                    .execute()
                )
                values = resp.get("values", [])
                if not values:
                    continue

                headers = [str(h).strip() for h in values[0]]
                headers_lower = [h.lower() for h in headers]

                # Определяем колонки сабов
                episodes_col_idx: Optional[int] = None
                checkbox_col_idx: Optional[int] = None

                # 1. Поиск явных колонок
                for c_idx, h in enumerate(headers_lower):
                    if h in {"subs status", "сабы", "статус сабов"}:
                        episodes_col_idx = c_idx
                    elif h in {"first subs", "первые сабы"}:
                        checkbox_col_idx = c_idx

                # 2. Если есть колонки с именем 'subs'
                subs_indices = [c_idx for c_idx, h in enumerate(headers_lower) if h == "subs"]
                if subs_indices:
                    for s_idx in subs_indices:
                        # Проверяем строки с данными для определения типа
                        is_checkbox = False
                        for r in values[1:]:
                            if len(r) > s_idx:
                                val_str = str(r[s_idx]).strip().upper()
                                if val_str in {"TRUE", "FALSE"}:
                                    is_checkbox = True
                                    break
                        if is_checkbox and checkbox_col_idx is None:
                            checkbox_col_idx = s_idx
                        elif not is_checkbox and episodes_col_idx is None:
                            episodes_col_idx = s_idx

                # Если не нашли явную колонку серий, но есть хотя бы одна subs
                if episodes_col_idx is None and subs_indices:
                    episodes_col_idx = subs_indices[0]

                # Ищем строку с тайтлом
                target_row_idx: Optional[int] = None
                shiki_str = str(shiki_id)

                for r_idx, row in enumerate(values[1:], start=2):
                    for cell in row:
                        cell_str = str(cell).strip()
                        if not cell_str:
                            continue
                        if cell_str == shiki_str or f"/animes/{shiki_str}" in cell_str or f"/{shiki_str}/" in cell_str:
                            target_row_idx = r_idx
                            break
                        match = re.search(r"/animes/(?:z|a)?(\d+)", cell_str)
                        if match and int(match.group(1)) == shiki_id:
                            target_row_idx = r_idx
                            break
                    if target_row_idx is not None:
                        break

                if target_row_idx is not None:
                    # Нашли строку! Формируем обновления
                    batch_data: list[dict[str, Any]] = []

                    # 1. Обновление серии
                    if episodes_col_idx is not None:
                        ep_letter = self.col_idx_to_letter(episodes_col_idx)
                        batch_data.append({
                            "range": f"'{sheet_name}'!{ep_letter}{target_row_idx}",
                            "values": [[episode_num]],
                        })

                    # 2. Обновление чекбокса первых сабов
                    if checkbox_col_idx is not None:
                        cb_letter = self.col_idx_to_letter(checkbox_col_idx)
                        # Проверяем текущее значение ячейки
                        curr_cb = ""
                        if len(values[target_row_idx - 1]) > checkbox_col_idx:
                            curr_cb = str(values[target_row_idx - 1][checkbox_col_idx]).strip().upper()

                        if curr_cb != "TRUE":
                            batch_data.append({
                                "range": f"'{sheet_name}'!{cb_letter}{target_row_idx}",
                                "values": [[True]],
                            })

                    if batch_data:
                        service.spreadsheets().values().batchUpdate(
                            spreadsheetId=spreadsheet_id,
                            body={
                                "valueInputOption": "USER_ENTERED",
                                "data": batch_data,
                            },
                        ).execute()
                        logger.info(
                            "Обновлена командная таблица %s на листе '%s' для тайтла %d (серия %d)",
                            spreadsheet_id,
                            sheet_name,
                            shiki_id,
                            episode_num,
                        )
                        return True

            return False

        return await asyncio.to_thread(_sync_find_and_update)


