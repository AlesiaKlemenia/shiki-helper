# Implementation Plan: Интерактивный Telegram UI на aiogram-dialog и Sandbox

**Track ID:** `bot_ui_dialogs_20261008`
**Type:** Feature
**Status:** Complete

---

## Phase 1: Middleware и управление сессиями БД

- [x] Task: Разработать `tests/test_middlewares.py` (TDD Red Phase)
  - [x] Тест внедрения `session` в `data` через `DbSessionMiddleware`
  - [x] Тест изоляции и закрытия сессии после выполнения хэндлера
  - [x] Тест переключения в `SandboxMiddleware`
- [x] Task: Реализовать `app/bot/middlewares/db.py` и `app/bot/middlewares/sandbox.py`
- [x] Task: Phase 1 Verification & Checkpoint

## Phase 2: Базовые команды и немедленная синхронизация (`/sync`)

- [x] Task: Разработать `tests/test_bot_handlers.py` (TDD Red Phase)
  - [x] Тест команды `/start` (создание пользователя, приветствие)
  - [x] Тест команды `/help`
  - [x] Тест команды `/sync` (вызов TrackerService, отправка дайджеста)
- [x] Task: Реализовать `app/bot/handlers/common.py` и `app/bot/handlers/manual.py`
- [x] Task: Phase 2 Verification & Checkpoint

## Phase 3: Диалоги aiogram-dialog (Онбординг и Тайтлы)

- [x] Task: Реализовать `app/bot/dialogs/onboarding/`
  - [x] Окно выбора таймзоны
  - [x] Окно выбора времени рассылки
  - [x] Окно привязки Google Sheets / пропуск
- [x] Task: Реализовать `app/bot/dialogs/titles/`
  - [x] Постраничный просмотр тайтлов
  - [x] Поиск тайтлов
- [x] Task: Подключить роутеры и `setup_dialogs(dp)` в `app/main.py`
- [x] Task: Phase 3 Verification & Checkpoint

## Phase 4: Верификация, линтинг и интеграция

- [x] Task: Запуск тестов и проверка качества
  - [x] `pytest tests/` — все тесты зелёные (94 теста успешно)
  - [x] `ruff check app/ tests/` — 0 ошибок
  - [x] `mypy app/` — 0 ошибок
- [x] Task: Фиксация завершения трека в conductor и Git коммит

