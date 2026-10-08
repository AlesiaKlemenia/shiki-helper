# Implementation Plan: Интерактивный Telegram UI на aiogram-dialog и Sandbox

**Track ID:** `bot_ui_dialogs_20261008`
**Type:** Feature
**Status:** In Progress

---

## Phase 1: Middleware и управление сессиями БД

- [ ] Task: Разработать `tests/test_middlewares.py` (TDD Red Phase)
  - [ ] Тест внедрения `session` в `data` через `DbSessionMiddleware`
  - [ ] Тест изоляции и закрытия сессии после выполнения хэндлера
  - [ ] Тест переключения в `SandboxMiddleware`
- [ ] Task: Реализовать `app/bot/middlewares/db.py` и `app/bot/middlewares/sandbox.py`
- [ ] Task: Phase 1 Verification & Checkpoint

## Phase 2: Базовые команды и немедленная синхронизация (`/sync`)

- [ ] Task: Разработать `tests/test_bot_handlers.py` (TDD Red Phase)
  - [ ] Тест команды `/start` (создание пользователя, приветствие)
  - [ ] Тест команды `/help`
  - [ ] Тест команды `/sync` (вызов TrackerService, отправка дайджеста)
- [ ] Task: Реализовать `app/bot/handlers/common.py` и `app/bot/handlers/manual.py`
- [ ] Task: Phase 2 Verification & Checkpoint

## Phase 3: Диалоги aiogram-dialog (Онбординг и Тайтлы)

- [ ] Task: Реализовать `app/bot/dialogs/onboarding/`
  - [ ] Окно выбора таймзоны
  - [ ] Окно выбора времени рассылки
  - [ ] Окно привязки Google Sheets / пропуск
- [ ] Task: Реализовать `app/bot/dialogs/titles/`
  - [ ] Постраничный просмотр тайтлов
  - [ ] Поиск тайтлов
- [ ] Task: Подключить роутеры и `setup_dialogs(dp)` в `app/main.py`
- [ ] Task: Phase 3 Verification & Checkpoint

## Phase 4: Верификация, линтинг и интеграция

- [ ] Task: Запуск тестов и проверка качества
  - [ ] `pytest tests/` — все тесты зелёные
  - [ ] `ruff check app/ tests/` — 0 ошибок
  - [ ] `mypy app/ tests/` — 0 ошибок
- [ ] Task: Фиксация завершения трека в conductor и Git коммит
