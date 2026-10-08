# Implementation Plan: Google Sheets API Client & OAuth Flow

**Track ID:** `google_sheets_client_20261008`
**Type:** Feature
**Status:** In Progress

---

## Phase 1: Модели данных и TDD-тесты для Google Sheets & OAuth

- [ ] Task: Создать DTO-модели для строк таблицы
  - [ ] Создать `SheetRow` модель для парсинга строк диапазона `A2:D`
  - [ ] Хелпер форматирования значения серий для колонки D: `{aired}/{total or '?'}`
- [ ] Task: Разработать Unit-тесты `tests/test_sheets_sync.py` (TDD Red Phase)
  - [ ] Тест генерации ссылки Google OAuth (scope, redirect_uri, client_id)
  - [ ] Тест обмена auth-кода на refresh_token и его шифрования
  - [ ] Тест пакетного парсинга строк диапазона `A2:D`
  - [ ] Тест фильтрации по статусам («В работе», «В планах», «Анонс») и игнорирования прочих
  - [ ] Тест пакетного обновления (`batchUpdate`) колонки D
  - [ ] Тест обработки ошибки `GoogleTokenRevokedError` при невалидном токене
- [ ] Task: Phase 1 Verification & Checkpoint

## Phase 2: Реализация клиентов в `app/clients/google_sheets.py`

- [ ] Task: Реализовать класс `GoogleOAuthHelper`
  - [ ] Метод генерации ссылки авторизации
  - [ ] Метод обмена кода на токены с интеграцией `TokenEncryptor`
- [ ] Task: Реализовать класс `GoogleSheetsClient`
  - [ ] Инициализация с `Credentials` (расшифровка refresh_token)
  - [ ] Метод `read_releases_range(spreadsheet_id: str) -> list[SheetRow]`
  - [ ] Метод `batch_update_episodes(spreadsheet_id: str, updates: list[tuple[int, str]]) -> int`
  - [ ] Оборачивание синхронных вызовов в `asyncio.to_thread`
- [ ] Task: Phase 2 Verification & Checkpoint

## Phase 3: Верификация, линтинг и интеграция

- [ ] Task: Запуск тестов и проверка покрытия
  - [ ] `pytest tests/test_sheets_sync.py` — все тесты зелёные
  - [ ] `ruff check app/ tests/` — 0 ошибок
  - [ ] `mypy app/ tests/` — 0 ошибок
- [ ] Task: Фиксация завершения трека в conductor и Git коммит
