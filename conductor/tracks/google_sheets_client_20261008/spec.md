# Specification: Google Sheets API Client & OAuth Flow

**Track ID:** `google_sheets_client_20261008`
**Type:** Feature
**Status:** Draft

---

## 1. Overview
Реализация Google OAuth 2.0 flow для авторизации пользователей Telegram-бота и асинхронного клиента Google Sheets API (`app/clients/google_sheets.py`). Клиент обеспечивает:
- Генерацию ссылки для авторизации в Google.
- Обмен авторизационного кода на токены с шифрованием `refresh_token` через `TokenEncryptor`.
- Пакетное чтение диапазона `A2:D` с фильтрацией по статусу («В работе», «В планах», «Анонс»).
- Пакетное обновление (`batchUpdate`) значений серий в колонке D (`{aired}/{total or '?'}`).
- Отслеживание отозванных токенов (`invalid_grant`, `GoogleTokenRevokedError`).

---

## 2. Requirements & Architecture

### 2.1. OAuth Flow
- Scopes: `https://www.googleapis.com/auth/spreadsheets`
- Redirect URI: `urn:ietf:wg:oauth:2.0:oob` (out-of-band) для ввода кода авторизации в чате бота.
- Генерация URL авторизации через `google_auth_oauthlib.flow.Flow`.
- Обмен кода на `Credentials` с извлечением `refresh_token`.
- Сохранение зашифрованного токена в БД (`google_credentials`).

### 2.2. Модели данных таблицы
- `SheetRow`:
  - `row_index: int` (1-based номер строки в Google Sheets, начиная с 2)
  - `title_name_ru: str` (Колонка A: русское название)
  - `shiki_link_or_id: str` (Колонка B: ссылка на Shikimori или ID тайтла)
  - `status: str` (Колонка C: статус тайтла)
  - `current_episodes_text: str` (Колонка D: текущий текст серий)
- Разрешенные статусы: `{"В работе", "В планах", "Анонс"}` (регистронезависимо с нормализацией пробелов).

### 2.3. Google Sheets Operations
- Чтение диапазона `A2:D`:
  - Использование Google Sheets API v4 (`spreadsheets().values().get`).
  - Парсинг строк и отсеивание пустых либо не подходящих по статусу записей.
- Пакетная запись в колонку D:
  - Метод `batch_update_episodes(spreadsheet_id, updates: list[tuple[int, str]])`:
  - Формирование `ValueRange` для каждой обновляемой ячейки `D{row_index}`.
  - Единый вызов `spreadsheets().values().batchUpdate` для сохранения квот API.

### 2.4. Обработка ошибок (Resilience & Security)
- При возникновении `RefreshError` или `invalid_grant` выбрасывается специфичное исключение `GoogleTokenRevokedError`.
- Все синхронные вызовы SDK Google оборачиваются в `asyncio.to_thread` для предотвращения блокировки event loop.

---

## 3. Acceptance Criteria
1. Класс `GoogleOAuthHelper` генерирует корректную ссылку авторизации и производит обмен кода на зашифрованные учетные данные.
2. Класс `GoogleSheetsClient` в `app/clients/google_sheets.py` реализует асинхронное чтение `A2:D` и пакетное обновление колонки D.
3. Фильтр статусов корректно оставляет только строки «В работе», «В планах», «Анонс».
4. Обработка ошибок четко идентифицирует `GoogleTokenRevokedError`.
5. Unit-тесты в `tests/test_sheets_sync.py` покрывают все ветви логики на 100%.
6. Линтер `ruff` и тайпчекер `mypy` проходят без ошибок.
