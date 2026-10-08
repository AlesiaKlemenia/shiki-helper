# Implementation Plan: Бизнес-логика трекинга, Полнотекстовый поиск (FTS5) и генерация дайджеста

**Track ID:** `tracker_search_digest_20261008`
**Type:** Feature
**Status:** In Progress

---

## Phase 1: Сервис дайджеста (DigestService) и TDD-тесты

- [ ] Task: Разработать `tests/test_digest.py` (TDD Red Phase)
  - [ ] Тест генерации сообщения с новыми сериями (эмодзи, HTML-теги, ссылки)
  - [ ] Тест генерации сообщения при отсутствии новых серий
  - [ ] Экранирование HTML-символов в названиях тайтлов (`<`, `>`, `&`)
- [ ] Task: Реализовать `app/services/digest.py`
  - [ ] DTO `TitleUpdateDelta`
  - [ ] Функция `format_digest_html(deltas: list[TitleUpdateDelta]) -> str`
- [ ] Task: Phase 1 Verification & Checkpoint

## Phase 2: Полнотекстовый поиск (SearchService) с FTS5 и fallback

- [ ] Task: Разработать `tests/test_search.py` (TDD Red Phase)
  - [ ] Тест нормализации букв «ё» -> «е»
  - [ ] Тест поиска по префиксу слова
  - [ ] Тест fallback на `ILIKE` при синтаксической ошибке FTS запроса
- [ ] Task: Реализовать `app/services/search.py`
  - [ ] Функция очистки и токенизации запроса `sanitize_fts_query`
  - [ ] Класс `SearchService` с методом `search_user_titles`
- [ ] Task: Phase 2 Verification & Checkpoint

## Phase 3: Сервис сверки серий (TrackerService)

- [ ] Task: Разработать `tests/test_tracker.py` (TDD Red Phase)
  - [ ] Тест сверки при источнике Google Таблица (вычисление дельты, вызов batchUpdate)
  - [ ] Тест сверки при источнике только БД (без Google Таблицы)
  - [ ] Тест игнорирования тайтлов, где новых серий нет (aired_new == aired_old)
  - [ ] Тест обновления записей в таблице `tracked_titles`
- [ ] Task: Реализовать `app/services/tracker.py`
  - [ ] Класс `TrackerService`
  - [ ] Интеграция с `ShikimoriGraphQLClient` и `GoogleSheetsClient`
- [ ] Task: Phase 3 Verification & Checkpoint

## Phase 4: Верификация, линтинг и интеграция

- [ ] Task: Запуск тестов и проверка качества
  - [ ] `pytest tests/` — все тесты зелёные
  - [ ] `ruff check app/ tests/` — 0 ошибок
  - [ ] `mypy app/ tests/` — 0 ошибок
- [ ] Task: Фиксация завершения трека в conductor и Git коммит
