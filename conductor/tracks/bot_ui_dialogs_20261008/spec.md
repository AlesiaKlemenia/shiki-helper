# Specification: Интерактивный Telegram UI на aiogram-dialog и Sandbox

**Track ID:** `bot_ui_dialogs_20261008`
**Type:** Feature
**Status:** Draft

---

## 1. Overview
Создание интерактивного пользовательского интерфейса Telegram-бота на базе `aiogram 3.x` и `aiogram-dialog`:
- Команды `/start`, `/help`, `/menu`, `/sync`.
- Диалог онбординга: выбор часового пояса, времени ежедневной рассылки, пошаговая авторизация в Google Sheets (или пропуск для ручного режима).
- Диалог просмотра списка тайтлов с постраничной пагинацией и поиском по названию.
- Middleware управления сессиями БД и поддержка режима песочницы Sandbox (Shadow DB) через `DynamicSessionMaker`.

---

## 2. Requirements & Architecture

### 2.1. Middleware
- `DbSessionMiddleware`: перехватывает апдейты aiogram, создает `AsyncSession` через фабрику сессий и передает объект `session` в `data` хэндлера.
- `SandboxMiddleware`: если для текущего пользователя активирован тестовый режим (или при переданном флаге тестирования), активирует sandbox в `DynamicSessionMaker`.

### 2.2. Команды и базовые обработчики (`app/bot/handlers/common.py`, `app/bot/handlers/manual.py`)
- `/start`: регистрация пользователя в таблице `users` (если новый) и запуск диалога онбординга либо приветствие существующего пользователя.
- `/menu`: открытие главного меню управления.
- `/sync`: запуск немедленной проверки обновлений через `TrackerService` с индикатором «🔍 Проверяем обновления...» и отправкой дайджеста.
- `/help`: краткая справка по возможностям бота.

### 2.3. Диалоги `aiogram-dialog`
1. `onboarding_dialog` (`app/bot/dialogs/onboarding/`):
   - Окно 1: Выбор таймзоны (кнопка «Europe/Moscow» по умолчанию, «Europe/Kyiv», «Asia/Almaty» или ручной ввод IANA).
   - Окно 2: Выбор времени дайджеста («19:00» по умолчанию, «12:00», «21:00» или ввод `HH:MM`).
   - Окно 3: Привязка Google Таблицы (кнопка-ссылка на Google OAuth, поле ввода кода авторизации, поле ввода ссылки на таблицу).
   - Кнопка «Пропустить привязку таблицы» для перехода в режим без Google Sheets.
2. `titles_dialog` (`app/bot/dialogs/titles/`):
   - Список отслеживаемых тайтлов пользователя с пагинацией (кнопки «◀️», «▶️»).
   - Кнопка «🔍 Поиск» для фильтрации по подстроке через `SearchService`.

---

## 3. Acceptance Criteria
1. Все роутеры и диалоги регистрируются в `Dispatcher` в `app/main.py`.
2. Middleware корректно внедряет `session` в контекст обработчиков.
3. Обработчик `/sync` вызывает `TrackerService` и отправляет форматированный HTML-дайджест.
4. Диалоги онбординга и тайтлов компилируются без ошибок `aiogram-dialog`.
5. Тесты в `tests/test_bot_handlers.py` и `tests/test_middlewares.py` покрывают логику.
6. `ruff check` и `mypy` не выдают ошибок.
