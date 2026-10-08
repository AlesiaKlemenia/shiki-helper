# Implementation Plan: Клиент Shikimori GraphQL API и Resilience

**Track ID:** `shikimori_client_20261008`
**Type:** Feature
**Status:** Complete

---

## Phase 1: Модели данных и TDD-тесты для клиента Shikimori

- [x] Task: Создать DTO-модели для ответов Shikimori
  - [x] Создать `AnimeInfo` модель с полями `id`, `name`, `russian`, `status`, `episodes`, `episodes_aired`, `url`
  - [x] Валидация camelCase `episodesAired` из GraphQL в snake_case `episodes_aired`
- [x] Task: Разработать комплексные Unit-тесты `tests/test_shikimori.py` (TDD Red Phase)
  - [x] Тест успешного парсинга GraphQL ответа в `list[AnimeInfo]`
  - [x] Тест чанкования списка ID (>50 элементов) на запросы по 50 тайтлов
  - [x] Тест наличия обязательного заголовка `User-Agent`
  - [x] Тест опциональной авторизации (Bearer токен в `Authorization`)
  - [x] Тест прозрачного fallback на публичный режим при HTTP 401
  - [x] Тест Retry с Exponential Backoff при HTTP 429 (учет `Retry-After`)
  - [x] Тест Retry при ошибках сервера HTTP 502/503/504
  - [x] Тест повторной попытки при пустом теле ответа
  - [x] Тест выброса `ShikimoriAPIError` при исчерпании всех попыток
- [x] Task: Phase 1 Verification & Checkpoint

## Phase 2: Реализация клиента ShikimoriGraphQLClient

- [x] Task: Реализовать `app/clients/shikimori.py`
  - [x] Класс исключения `ShikimoriAPIError`
  - [x] Асинхронный контекстный менеджер / HTTP-сессия через `httpx.AsyncClient`
  - [x] Метод отправки GraphQL-запроса с циклом retry (exponential backoff + jitter)
  - [x] Метод `fetch_animes_by_ids(ids: list[int]) -> list[AnimeInfo]` с чанкованием
  - [x] Корректное закрытие сессий клиента
- [x] Task: Phase 2 Verification & Checkpoint

## Phase 3: Верификация, линтинг и интеграция

- [x] Task: Запуск тестов и проверка покрытия
  - [x] `pytest tests/test_shikimori.py` — 11 тестов зелёные (всего 64 теста в проекте)
  - [x] `ruff check app/ tests/` — 0 ошибок
  - [x] `mypy app/ tests/` — 0 ошибок
- [x] Task: Фиксация завершения трека в conductor и Git коммит

