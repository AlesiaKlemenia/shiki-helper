# Implementation Plan: Планировщик APScheduler, Healthcheck, Бэкапы и Recovery

**Track ID:** `scheduler_backup_health_20261008`
**Type:** Feature
**Status:** Complete

---

## Phase 1: Сервис бэкапа базы данных (BackupService)

- [x] Task: Разработать `tests/test_backup.py` (TDD Red Phase)
  - [x] Тест создания дампа/копии SQLite базы в поток байт
  - [x] Тест отправки бэкапа в Telegram администратору
- [x] Task: Реализовать `app/services/backup.py`
- [x] Task: Phase 1 Verification & Checkpoint

## Phase 2: Планировщик фоновых задач (SchedulerService)

- [x] Task: Разработать `tests/test_scheduler.py` (TDD Red Phase)
  - [x] Тест регистрации персональных крон-задач рассылки дайджеста для пользователей
  - [x] Тест периодической задачи резервного копирования (раз в 24ч в 03:00 UTC)
  - [x] Тест корректного shutdown планировщика
- [x] Task: Реализовать `app/services/scheduler.py`
- [x] Task: Phase 2 Verification & Checkpoint

## Phase 3: HTTP Healthcheck сервер и совместимость с Render ($PORT)

- [x] Task: Разработать `tests/test_healthcheck.py` (TDD Red Phase)
  - [x] Тест ответа `GET /health` со статусом `200 OK`, uptime и статусом сервиса
- [x] Task: Реализовать `app/services/health.py` (фоновый сервер `aiohttp.web` с чтением `$PORT`)
- [x] Task: Phase 3 Verification & Checkpoint

## Phase 4: Интеграция в app/main.py, Lifespan и устойчивость (Recovery)

- [x] Task: Подключить планировщик, health-сервер и стартовые проверки в `app/main.py`
- [x] Task: Реализовать стартовое и аварийное оповещение администратора о статусе БД
- [x] Task: Запуск тестов, проверка линтером ruff и типизации mypy (99 тестов pass)
- [x] Task: Фиксация завершения трека в Conductor, PLAN.md и коммит в Git

