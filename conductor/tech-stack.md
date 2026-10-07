# Technology Stack: Shiki-Helper

## Language & Runtime

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.11+ |
| Package Manager | pip + venv | latest |

## Telegram Bot

| Component | Technology | Notes |
|-----------|-----------|-------|
| Bot Framework | `aiogram` | 3.x (async) |
| Interactive UI | `aiogram-dialog` | stateful FSM-dialogs |
| FSM Storage | Redis → MemoryStorage (fallback) | RedisStorage с graceful degradation |

## Database & ORM

| Component | Technology | Notes |
|-----------|-----------|-------|
| Primary DB | PostgreSQL (Supabase/Neon) или SQLite | asyncpg для PG, aiosqlite для SQLite |
| ORM | SQLAlchemy 2.0 (async) | Declarative models |
| Migrations | Alembic | async env |
| FTS | SQLite FTS5 | BM25, нормализация ё→е, fallback на ILIKE |
| Shadow DB | in-memory SQLite via ContextVar | Sandbox режим для тестирования UI |

## Caching & State

| Component | Technology | Notes |
|-----------|-----------|-------|
| Cache & FSM | Redis | Персистентное хранение + distributed locks |
| Fallback | MemoryStorage (aiogram) | При недоступности Redis |

## External APIs

| Component | Technology | Notes |
|-----------|-----------|-------|
| Shikimori | GraphQL API (`/api/graphql`) | batching 50 тайтлов, User-Agent обязателен |
| HTTP Client | `httpx` / `aiohttp` | async |
| Rate Limiter | `aiolimiter` | 5 rps / 90 rpm |
| Google Sheets | `google-api-python-client` / `gspread-asyncio` | batchUpdate, OAuth 2.0 |
| Google Auth | `google-auth`, `google-auth-oauthlib` | refresh_token stored encrypted |

## Security

| Component | Technology | Notes |
|-----------|-----------|-------|
| Token Encryption | `cryptography` (Fernet) | OAuth refresh_token шифруется ключом из .env |
| Secrets | pydantic-settings (BaseSettings) | Чтение из .env, валидация при старте |

## Scheduling

| Component | Technology | Notes |
|-----------|-----------|-------|
| Task Scheduler | APScheduler 3.x | AsyncIOScheduler, misfire_grace_time |
| Scheduler Storage | SQLAlchemy JobStore | Персистентные джобы |

## Infrastructure

| Component | Technology | Notes |
|-----------|-----------|-------|
| Containerization | Docker + docker-compose | Локальный Redis в compose |
| Health Check | `aiohttp.web` | `GET /health` на `$PORT` |
| Deployment | Render.com | Docker Web Service |
| DB Hosting | Supabase / Neon | Бесплатный PostgreSQL |
| Redis Hosting | Upstash | Serverless Redis |

## Testing

| Component | Technology | Notes |
|-----------|-----------|-------|
| Test Runner | `pytest` + `pytest-asyncio` | |
| Mocking | `pytest-mock`, `unittest.mock` | |
| Coverage | `pytest-cov` | Target: >80% |
| HTTP Mocking | `respx` / `aioresponses` | Для тестирования HTTP-клиентов |

## Development Commands

### Setup
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Заполнить .env переменными окружения
alembic upgrade head
```

### Daily Development
```bash
# Запуск бота локально
docker-compose up -d  # Поднять Redis и PostgreSQL (если локально)
python -m app.main

# Тесты
pytest tests/ -v
pytest tests/ --cov=app --cov-report=html

# Линтинг
ruff check app/
mypy app/
```

### Before Committing
```bash
ruff check app/ tests/
mypy app/
pytest tests/ --cov=app --cov-fail-under=80
```
