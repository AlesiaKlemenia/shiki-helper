# План разработки Telegram-бота Shiki-Helper

## 1. Обзор проекта и архитектурные решения

### 1.1. Назначение
Автоматизированный Telegram-бот для саб-мейкеров и релиз-групп:
- Мониторинг выхода новых серий аниме через официальный Shikimori API v1/v2.
- Персональные и групповые ежедневные дайджесты с учетом часовых поясов.
- Двусторонняя синхронизация с Google Таблицами рабочих релизов через Google Sheets API v4.
- Принудительное обновление состояния по требованию через Telegram UI.

### 1.2. Технологический стек
- **Язык**: Python 3.11+
- **Фреймворк бота**: `aiogram 3.x` (асинхронный Telegram Bot API)
- **Интерактивные меню и формы**: `aiogram-dialog` (stateful UI-компоненты: онбординг, настройки времени/таймзоны, пагинация тайтлов)
- **Хранилище состояний и кэша**: `Redis` (персистентное хранилище FSM состояний aiogram / aiogram-dialog через `RedisStorage` с graceful degradation на `MemoryStorage` при сбое, кэширование запросов Shikimori и распределённые блокировки)
- **База данных**: PostgreSQL (внешняя БД на Supabase / Neon для деплоя на Render, с поддержкой локального подключения через asyncpg) или SQLite с полнотекстовым поиском FTS5
- **Полнотекстовый поиск (FTS5)**: SQLite FTS5 (BM25 ранжирование, нормализация «ё» → «е», префиксный поиск и автоматический fallback на `ILIKE` при синтаксических ошибках поискового запроса)
- **ORM и миграции**: `SQLAlchemy 2.0 (async)` + `Alembic`
- **Тестовый режим / Sandbox (Shadow DB)**: механизм подмены `AsyncSession` через `ContextVar` на in-memory базу для безопасного тестирования UI и админских операций без риска повредить боевые данные
- **Планировщик задач**: `APScheduler 3.x` (AsyncIOScheduler) с защитой `misfire_grace_time`, корректным graceful shutdown в `finally`/lifespan и персистентным хранением джобов
- **API Shikimori**: `GraphQL API` (`https://shikimori.one/api/graphql`) — точечный запрос полей (`id`, `name`, `russian`, `status`, `episodes`, `episodesAired`, `url`), батчинг до 50 тайтлов за 1 запрос, exponential backoff (retry при 429/502/503/504) и автоматический fallback
- **HTTP-клиент & Rate Limiter**: `httpx` / `aiohttp` + `aiolimiter` (жесткий контроль лимита 5 rps / 90 rpm)
- **Google Sheets API**: `google-auth`, `google-auth-oauthlib`, `google-api-python-client` / `gspread-asyncio` с обработкой `GoogleTokenRevokedError` / `invalid_grant` и алертом администратору
- **Резервное копирование**: асинхронный бэкап базы данных (`sqlite3.backup()` в `asyncio.to_thread` / dump PG) с отправкой архива в закрытый сервисный Telegram-топик по cron
- **Веб-сервер проверки здоровья**: встроенный лёгкий `aiohttp.web` эндпоинт (`GET /health`) на порту `$PORT` для предотвращения усыпления Render.com
- **Надёжность и Recovery Alerts**: отправка уведомлений администратору/пользователям при холодном старте, падении или восстановлении подключения к БД
- **Контейнеризация**: `Docker` + `docker-compose`

---

## 2. Структура проекта

```text
shiki-helper/
├── .env.example              # Шаблон переменных окружения
├── .gitignore                # Исключения git (venv, credentials, .env, __pycache__)
├── Dockerfile                # Сборка контейнера для Render / локального запуска
├── docker-compose.yml        # Локальный запуск сервиса
├── README.md                 # Документация по настройке и запуску
├── requirements.txt          # Зависимости проекта
├── alembic.ini               # Конфигурация миграций БД
├── migrations/               # Версии миграций Alembic
├── app/
│   ├── __init__.py
│   ├── main.py               # Точка входа: запуск aiogram, APScheduler и healthcheck сервера
│   ├── config.py             # Pydantic BaseSettings (чтение env, валидация)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py       # Шифрование OAuth токенов (Fernet)
│   │   └── logger.py         # Настройка структурированного логирования
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── shikimori.py      # Клиент Shikimori API с aiolimiter и батчингом ids
│   │   └── google_sheets.py  # Клиент Google Sheets API (OAuth авторизация, batch-чтение/запись)
│   ├── db/
│   │   ├── __init__.py
│   │   ├── session.py        # Async engine и sessionmaker
│   │   ├── models.py         # SQLAlchemy модели: User, TrackedTitle, GoogleAuth, TitleSnapshot
│   │   └── repositories/     # Data Access Layer (CRUD для пользователей и тайтлов)
│   │       ├── user_repo.py
│   │       └── title_repo.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── tracker.py        # Бизнес-логика сверки серий и формирования дельты
│   │   ├── sheets_sync.py    # Синхронизация: парсинг A-C, фильтр статусов, обновление D
│   │   └── digest.py         # Форматирование красивых сообщений-дайджестов
│   ├── scheduler/
│   │   ├── __init__.py
│   │   └── tasks.py          # Регистрация ежедневных задач в APScheduler
│   └── bot/
│       ├── __init__.py
│       ├── dialogs/          # Диалоги на базе aiogram-dialog
│       │   ├── __init__.py
│       │   ├── onboarding/   # Диалог онбординга (OAuth, таймзона, время рассылки)
│       │   ├── settings/     # Диалог настроек пользователя
│       │   └── titles/       # Диалог управления тайтлами
│       ├── handlers/         # Базовые роутеры aiogram
│       │   ├── common.py     # /start, /help, вход в диалоги
│       │   └── manual.py     # Кнопка «Обновить сейчас», принудительный чек
│       ├── middlewares/      # Проверка прав доступа, передача сессии БД
│       └── recovery.py       # Логика оповещения при старте/восстановлении бота и БД
└── tests/                    # Модульные тесты (pytest, pytest-asyncio)
    ├── __init__.py
    ├── test_shikimori.py     # Тесты парсинга серий и лимитеров
    ├── test_tracker.py       # Тесты вычисления дельты новых серий
    └── test_sheets_sync.py   # Тесты фильтрации статусов и маппинга колонок A-D
```

---

## 3. Модель данных (Схема БД)

1. **`users`**:
   - `telegram_id` (BigInteger, Primary Key)
   - `username` (String, nullable)
   - `timezone` (String, default "Europe/Moscow")
   - `delivery_time` (Time, default "19:00:00")
   - `is_active` (Boolean, default True)
   - `created_at` (DateTime UTC)

2. **`google_credentials`**:
   - `user_id` (BigInteger, Foreign Key -> `users.telegram_id`)
   - `encrypted_refresh_token` (Text) — зашифрован ключом из `.env`
   - `token_uri` (String)
   - `client_id` (String)
   - `client_secret` (String)
   - `scopes` (JSON / Text)
   - `spreadsheet_id` (String, nullable)

3. **`tracked_titles`**:
   - `id` (Integer, Primary Key, autoincrement)
   - `user_id` (BigInteger, Foreign Key -> `users.telegram_id`)
   - `shiki_id` (Integer, Index) — ID тайтла на Shikimori
   - `title_name_ru` (String) — Русское название из колонки A
   - `status_in_table` (String) — «В работе», «В планах», «Анонс»
   - `row_index` (Integer, nullable) — Индекс строки в Google Таблице для точечного обновления
   - `last_episodes_aired` (Integer, default 0) — Последнее зафиксированное количество серий
   - `total_episodes` (Integer, nullable) — Всего серий по плану (или None/?)
   - `updated_at` (DateTime UTC)

---

## 4. Этапы разработки

### Этап 1: Инфраструктурный каркас, База Данных и Redis
- [ ] Инициализация структуры файлов и каталогов проекта в `E:\shiki-helper`.
- [ ] Оформление `.env.example`, `requirements.txt` (с `redis`, `asyncpg`, `aiogram-dialog`), `Dockerfile` и `docker-compose.yml` (с локальным контейнером Redis).
- [ ] Настройка асинхронного подключения к БД через SQLAlchemy (`app/db/session.py`).
- [ ] Конфигурация Redis FSM с graceful degradation: проверка `PING` при старте и автоматический fallback на `MemoryStorage`, если Redis недоступен.
- [ ] Shadow DB / Sandbox mode: реализация `DynamicSessionMaker` с поддержкой `ContextVar` для переключения сессии пользователя в in-memory SQLite при включенном тестовом режиме админки.
- [ ] Описание моделей (`User`, `GoogleAuth`, `TrackedTitle`) и настройка миграций Alembic.
- [ ] Реализация шифрования OAuth токенов через `cryptography.fernet` (`app/core/security.py`).

### Этап 2: Клиент Shikimori GraphQL API и Resilience
- [ ] Реализация `ShikimoriGraphQLClient` (`app/clients/shikimori.py`):
  - Обязательный заголовок `User-Agent`.
  - Интеграция `aiolimiter.AsyncLimiter` (максимум 5 rps / 90 rpm).
  - Эффективный GraphQL-запрос:
    ```graphql
    query($ids: String, $limit: Int) {
      animes(ids: $ids, limit: $limit) {
        id
        name
        russian
        status
        episodes
        episodesAired
        url
      }
    }
    ```
  - Метод пакетного получения данных (`fetch_animes_by_ids(ids: list[int])`) с автоматическим чанкованием по 50 тайтлов.
  - Полноценная стратегия отказоустойчивости (Resilience):
    - Exponential backoff c jitter на HTTP 429, 502, 503, 504.
    - Автоматический refresh токена при HTTP 401 и fallback на гостевой режим.
    - Повторный запрос при пустом ответе.
- [ ] Написание Unit-тестов для парсера ответов Shikimori GraphQL и сценариев retry/fallback (`tests/test_shikimori.py`).

### Этап 3: Клиент Google Sheets API & OAuth Flow
- [ ] Создание вспомогательного модуля формирования ссылки авторизации Google OAuth 2.0.
- [ ] Реализация механизма обмена кода авторизации на токены и безопасного сохранения в БД.
- [ ] Реализация `GoogleSheetsClient` (`app/clients/google_sheets.py`):
  - Метод пакетного чтения диапазона `A2:D` таблицы.
  - Фильтрация строк по статусу (колонка C): только «В работе», «В планах», «Анонс».
  - Формирование данных для записи: колонка D в формате `{episodes_aired}/{episodes or '?'}`.
  - Метод пакетного обновления (`batchUpdate`) колонки D для экономии квот Google API.
  - Отлов критических ошибок авторизации (`GoogleTokenRevokedError`, `invalid_grant`) с уведомлением администратора/пользователя вместо зацикливания.
- [ ] Написание Unit-тестов на логику фильтрации, подготовки строк и обработки ошибок (`tests/test_sheets_sync.py`).

### Этап 4: Бизнес-логика трекинга, Полнотекстовый поиск (FTS5) и генерация дайджеста
- [ ] Сервис `TrackerService` (`app/services/tracker.py`):
  - Загрузка актуального состояния из таблицы Google (или из БД при ручном вводе).
  - Сравнение с базой данных: определение тайтлов, где вышли новые серии ($\text{aired}_{\text{new}} > \text{aired}_{\text{old}}$).
  - Обновление колонки D в Google Sheets.
  - Сохранение нового состояния в таблицу `tracked_titles`.
- [ ] Сервис быстрого поиска тайтлов:
  - SQLite FTS5 индекс с BM25-ранжированием.
  - Нормализация букв `ё` $\to$ `е` и префиксный поиск.
  - Автоматический fallback на `ILIKE` при ошибке синтаксиса FTS запроса.
- [ ] Сервис `DigestService` (`app/services/digest.py`):
  - Формирование аккуратного сообщения для Telegram с эмодзи, русским названием, количеством новых серий и ссылками.

### Этап 5: Интерактивный Telegram UI на `aiogram-dialog` и Sandbox
- [ ] Главное меню и базовые команды (`/start`, `/help`, `/menu`).
- [ ] Настройка `aiogram-dialog` (DialogManager, Window, Jinja/Formatters).
- [ ] Диалог онбординга:
  - Выбор/ввод часового пояса и времени ежедневного дайджеста.
  - Пошаговая привязка Google OAuth (инструкция, кнопка-ссылка на авторизацию, ввод кода/токена).
  - Ввод ссылки на Google Таблицу (валидация Spreadsheet ID).
  - Альтернативный режим: ручной ввод списка ID/названий без таблицы.
- [ ] Диалог настроек и списка тайтлов с пагинацией и поиском по FTS5.
- [ ] Middleware для тестового режима (Sandbox / Shadow DB): включение изоляции для безопасного тестирования интерфейса.
- [ ] Кнопка / команда «Обновить сейчас» (`/sync`): запуск немедленной проверки с индикатором выполнения.

### Этап 6: Планировщик APScheduler, Резервное копирование, Healthcheck и Recovery
- [ ] Интеграция `AsyncIOScheduler`:
  - Динамическая регистрация задач рассылки для каждого пользователя на основе его `delivery_time` и `timezone`.
  - Настройка `misfire_grace_time` для предотвращения всплеска накопленных задач после рестарта.
  - Корректный graceful shutdown планировщика в блоке `finally` / lifespan-хэндлерах.
- [ ] Резервное копирование БД в Telegram:
  - Создание консистентного снапшота через `sqlite3.backup()` в `asyncio.to_thread` (или pg_dump).
  - Периодическая фоновая отправка файла бэкапа в закрытый сервисный топик/чат администратора по крону.
- [ ] Мониторинг работоспособности и оповещения о сбоях/восстановлении:
  - Механизм `Lifespan / on_startup`: проверка доступности БД и внешних API при старте сервиса.
  - Оповещение администратора/пользователей о перезапуске/восстановлении бота («🟢 Бот успешно запущен и восстановил соединение с базой данных»).
  - Защитный контур фонового чекера: если подключение к БД или API кратковременно рвётся, бот не падает намертво, а пишет лог и переподключается с экспоненциальной задержкой. При восстановлении связи — подтверждающее уведомление.
- [ ] Реализация фонового HTTP-сервера на `aiohttp.web`:
  - Маршрут `GET /health` возвращает статус `200 OK` и базовые метрики (uptime, статус бота).
  - Обеспечение совместимости с переменной `$PORT` на Render.
- [ ] Сборка и проверка запуска через `docker-compose up --build`.

---

## 5. Инструкция по подготовке окружения (Render + Neon/Supabase)

1. **Создание базы данных и Redis (бесплатно)**:
   - **PostgreSQL**: Зарегистрироваться на [Neon.tech](https://neon.tech) или [Supabase.com](https://supabase.com), создать проект и скопировать строку подключения `postgresql+asyncpg://...`.
   - **Redis**: Зарегистрироваться на [Upstash.com](https://upstash.com) (Serverless Redis с бесплатным тарифом на 10 000 команд/день, идеален для Render/облака) и скопировать `REDIS_URL` вида `rediss://default:...@...upstash.io:6379`. (Для локальной разработки Redis уже поднимется в `docker-compose.yml`).
2. **Создание OAuth учетных данных Google**:
   - В Google Cloud Console создать проект, включить `Google Sheets API` и `Google Drive API`.
   - Настроить OAuth Consent Screen и создать OAuth 2.0 Client ID (тип: Desktop или Web Application).
   - Получить `GOOGLE_CLIENT_ID` и `GOOGLE_CLIENT_SECRET`.
3. **Деплой на Render.com**:
   - Создать новый `Web Service`, подключить Git-репозиторий.
   - Среда выполнения: `Docker`.
   - Заполнить переменные в `Environment`:
     * `BOT_TOKEN`: токен от @BotFather.
     * `DATABASE_URL`: строка подключения к PostgreSQL.
     * `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`.
     * `ENCRYPTION_KEY`: 32-байтный ключ Fernet для защиты токенов.
   - Для предотвращения усыпления подключить бесплатный пингер ([cron-job.org](https://cron-job.org) или UptimeRobot) на адрес `https://<your-render-app>.onrender.com/health` с интервалом раз в 10 минут.
