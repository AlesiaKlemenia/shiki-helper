# Implementation Plan: Бизнес-логика трекинга, Полнотекстовый поиск (FTS5) и генерация дайджеста

**Track ID:** `tracker_search_digest_20261008`
**Type:** Feature
**Status:** Complete

---

## Phase 1: Сервис дайджеста (DigestService) и TDD-тесты

- [x] Task: Разработать `tests/test_digest.py` (TDD Red Phase)
  - [x] Тест генерации сообщения с новыми сериями (эмодзи, HTML-теги, ссылки)
  - [x] Тест генерации сообщения при отсутствии новых серий
  - [x] Экранирование HTML-символов в названиях тайтлов (`<`, `>`, `&`)
- [x] Task: Реализовать `app/services/digest.py`
  - [x] DTO `TitleUpdateDelta`
  - [x] Функция `format_digest_html(deltas: list[TitleUpdateDelta]) -> str`
- [x] Task: Phase 1 Verification & Checkpoint

## Phase 2: Полнотекстовый поиск (SearchService) с FTS5 и fallback

- [x] Task: Разработать `tests/test_search.py` (TDD Red Phase)
  - [x] Тест нормализации букв «ё» -> «е»
  - [x] Тест поиска по префиксу слова
  - [x] Тест fallback на `ILIKE` при синтаксической ошибке FTS запроса
- [x] Task: Реализовать `app/services/search.py`
  - [x] Функция очистки и токенизации запроса `sanitize_fts_query`
  - [x] Класс `SearchService` с методом `search_user_titles`
- [x] Task: Phase 2 Verification & Checkpoint

## Phase 3: Сервис сверки серий (TrackerService)

- [x] Task: Разработать `tests/test_tracker.py` (TDD Red Phase)
  - [x] Тест сверки при источнике Google Таблица (вычисление дельты, вызов batchUpdate)
  - [x] Тест сверки при источнике только БД (без Google Таблицы)
  - [x] Тест игнорирования тайтлов, где новых серий нет (aired_new == aired_old)
  - [x] Тест обновления записей в таблице `tracked_titles`
- [x] Task: Реализовать `app/services/tracker.py`
  - [x] Класс `TrackerService`
  - [x] Интеграция с `ShikimoriGraphQLClient` и `GoogleSheetsClient`
- [x] Task: Phase 3 Verification & Checkpoint

## Phase 4: Верификация, линтинг и интеграция

- [x] Task: Запуск тестов и проверка качества
  - [x] `pytest tests/` — 88 тестов зелёные
  - [x] `ruff check app/ tests/` — 0 ошибок
  - [x] `mypy app/ tests/` — 0 ошибок
- [x] Task: Фиксация завершения трека в conductor и Git коммит
