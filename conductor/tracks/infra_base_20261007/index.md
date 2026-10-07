# Track: infra_base_20261007

## Documents

- [Specification](./spec.md)
- [Implementation Plan](./plan.md)
- [Metadata](./metadata.json)

## Overview

**Инфраструктурный каркас, База Данных и Redis** — реализует полный фундамент проекта:
структуру файлов, конфигурацию, async подключение к БД, Redis FSM с graceful degradation,
Shadow DB / Sandbox mode, SQLAlchemy модели, миграции Alembic и шифрование OAuth-токенов.

Соответствует **Этапу 1** из `PLAN.md`.
