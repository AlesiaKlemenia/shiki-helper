# Implementation Plan: Клиент Shikimori GraphQL API и Resilience

**Track ID:** `shikimori_client_20261008`
**Type:** Feature
**Status:** In Progress

---

## Phase 1: Модели данных и TDD-тесты для клиента Shikimori

- [ ] Task: Создать DTO-модели для ответов Shikimori
  - [ ] Создать `AnimeInfo` модель с полями `id`, `name`, `russian`, `status`, `episodes`, `episodes_aired`, `url`
  - [ ] Валидация camelCase `episodesAired` из GraphQL в snake_case `episodes_aired`
- [ ] Task: Разработать комплексные Unit-тесты `tests/test_shikimori.py` (TDD Red Phase)
  - [ ] Тест успешного парсинга GraphQL ответа в `list[AnimeInfo]`
  - [ ] Тест чанкования списка ID (>50 элементов) на запросы по 50 тайтлов
  - [ ] Тест наличия обязательного заголовка `User-Agent`
  - [ ] Тест опциональной авторизации (Bearer токен в `Authorization`)
  - [ ] Тест прозрачного fallback на публичный режим при HTTP 401
  - [ ] Тест Retry с Exponential Backoff при HTTP 429 (учет `Retry-After`)
  - [ ] Тест Retry при ошибках сервера HTTP 502/503/504
  - [ ] Тест повторной попытки при пустом теле ответа
  - [ ] Тест выброса `ShikimoriAPIError` при исчерпании всех попыток
- [ ] Task: Phase 1 Verification & Checkpoint

## Phase 2: Реализация клиента ShikimoriGraphQLClient

- [ ] Task: Реализовать `app/clients/shikimori.py`
  - [ ] Класс исключения `ShikimoriAPIError`
  - [ ] Асинхронный контекстный менеджер / HTTP-сессия через `httpx.AsyncClient`
  - [ ] Метод отправки GraphQL-запроса с циклом retry (exponential backoff + jitter)
  - [ ] Метод `fetch_animes_by_ids(ids: list[int]) -> list[AnimeInfo]` с чанкованием
  - [ ] Корректное закрытие сессий клиента
- [ ] Task: Phase 2 Verification & Checkpoint

## Phase 3: Верификация, линтинг и интеграция

- [ ] Task: Запуск тестов и проверка покрытия
  - [ ] `pytest tests/test_shikimori.py` — все тесты зелёные
  - [ ] `ruff check app/ tests/` — 0 ошибок
  - [ ] `mypy app/ tests/` — 0 ошибок
- [ ] Task: Фиксация завершения трека в conductor и Git коммит
