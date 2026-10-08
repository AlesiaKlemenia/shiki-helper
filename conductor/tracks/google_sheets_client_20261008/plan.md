# Implementation Plan: Google Sheets API Client & OAuth Flow

**Track ID:** `google_sheets_client_20261008`
**Type:** Feature
**Status:** Complete

---

## Phase 1: Модели данных и TDD-тесты для Google Sheets & OAuth

- [x] Task: Создать DTO-модели для строк таблицы
  - [x] Создать `SheetRow` модель для парсинга строк диапазона `A2:D`
  - [x] Хелпер форматирования значения серий для колонки D: `{aired}/{total or '?'}`
- [x] Task: Разработать Unit-тесты `tests/test_sheets_sync.py` (TDD Red Phase)
  - [x] Тест генерации ссылки Google OAuth (scope, redirect_uri, client_id)
  - [x] Тест обмена auth-кода на refresh_token и его шифрования
  - [x] Тест пакетного парсинга строк диапазона `A2:D`
  - [x] Тест фильтрации по статусам («В работе», «В планах», «Анонс») и игнорирования прочих
  - [x] Тест пакетного обновления (`batchUpdate`) колонки D
  - [x] Тест обработки ошибки `GoogleTokenRevokedError` при невалидном токене
- [x] Task: Phase 1 Verification & Checkpoint

## Phase 2: Реализация клиентов в `app/clients/google_sheets.py`

- [x] Task: Реализовать класс `GoogleOAuthHelper`
  - [x] Метод генерации ссылки авторизации
  - [x] Метод обмена кода на токены с интеграцией `TokenEncryptor`
- [x] Task: Реализовать класс `GoogleSheetsClient`
  - [x] Инициализация с `Credentials` (расшифровка refresh_token)
  - [x] Метод `read_releases_range(spreadsheet_id: str) -> list[SheetRow]`
  - [x] Метод `batch_update_episodes(spreadsheet_id: str, updates: list[tuple[int, str]]) -> int`
  - [x] Оборачивание синхронных вызовов в `asyncio.to_thread`
- [x] Task: Phase 2 Verification & Checkpoint

## Phase 3: Верификация, линтинг и интеграция

- [x] Task: Запуск тестов и проверка покрытия
  - [x] `pytest tests/test_sheets_sync.py` — 11 тестов зелёные (всего 75 тестов в проекте)
  - [x] `ruff check app/ tests/` — 0 ошибок
  - [x] `mypy app/ tests/` — 0 ошибок
- [x] Task: Фиксация завершения трека в conductor и Git коммит
