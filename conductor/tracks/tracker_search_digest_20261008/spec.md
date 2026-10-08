# Specification: Бизнес-логика трекинга, Полнотекстовый поиск (FTS5) и генерация дайджеста

**Track ID:** `tracker_search_digest_20261008`
**Type:** Feature
**Status:** Draft

---

## 1. Overview
Реализация ядра бизнес-логики Shiki-Helper:
1. `TrackerService` (`app/services/tracker.py`):
   - Загрузка актуального списка релизов (из Google Таблицы либо из базы данных при ручном вводе).
   - Запрос актуальных данных о вышедших сериях через `ShikimoriGraphQLClient`.
   - Вычисление дельты новых серий ($\text{aired}_{\text{new}} > \text{aired}_{\text{old}}$).
   - Пакетное обновление колонки D в Google Sheets через `GoogleSheetsClient.batch_update_episodes()`.
   - Синхронизация состояния в таблице `tracked_titles` базы данных.
2. `SearchService` (`app/services/search.py`):
   - Полнотекстовый поиск по отслеживаемым тайтлам пользователя.
   - Поддержка SQLite FTS5 (BM25 ранжирование, префиксный поиск `*`, нормализация букв `ё` $\to$ `е`).
   - Автоматический fallback на `ILIKE` при ошибках синтаксиса FTS или на других диалектах БД.
3. `DigestService` (`app/services/digest.py`):
   - Форматирование понятного и красивого дайджеста для Telegram (HTML/Markdown) с группировкой по релизам, эмодзи, номерами новых серий и кликабельными ссылками на Shikimori.

---

## 2. Requirements & Architecture

### 2.1. TrackerService (`app/services/tracker.py`)
- DTO `TitleUpdateDelta`:
  - `title_name_ru: str`
  - `shiki_id: int`
  - `old_episodes_aired: int`
  - `new_episodes_aired: int`
  - `total_episodes: Optional[int]`
  - `shikimori_url: str`
  - `delta: int` (количество новых серий)
- Метод `check_user_updates(user_id: int) -> list[TitleUpdateDelta]`:
  - Получает настройки пользователя и его Google credentials (если привязаны).
  - Считывает тайтлы: из Google Таблицы (при наличии) или из `tracked_titles`.
  - Запрашивает через `ShikimoriGraphQLClient.fetch_animes_by_ids()` актуальное число серий.
  - Находит разницу: если `aired_new > aired_old`, формирует дельту.
  - Пакетно обновляет Google Sheets (если привязана).
  - Обновляет `last_episodes_aired` и `updated_at` в БД.
  - Возвращает список `TitleUpdateDelta` для отправки дайджеста.

### 2.2. SearchService (`app/services/search.py`)
- Нормализатор строк: удаление спецсимволов FTS, замена `ё` $\to$ `е`, `Ё` $\to$ `Е`, добавление префикса `*` к токенам.
- Метод `search_titles(user_id: int, query: str) -> list[TrackedTitle]`:
  - Сначала пробует выполнить FTS5 match запрос по виртуальной таблице `tracked_titles_fts` с ранжированием `bm25`.
  - При возникновении любой ошибки синтаксиса (например, незакрытые кавычки) или на non-FTS backend — прозрачный fallback на `title_name_ru ILIKE '%query%'`.

### 2.3. DigestService (`app/services/digest.py`)
- Форматирует список `list[TitleUpdateDelta]` в Telegram HTML сообщение:
  - Заголовок с датой и эмодзи (например: `🔔 <b>Новые серии за сегодня:</b>`).
  - Строки релизов: `• <a href="{url}">{title}</a> — вышла <b>{new}</b> серия (было {old}/{total})`.
  - Если дельта пустая (`list` пуст): формирует сообщение `«Новых серий пока не выходило. Все релизы проверены!»`.

---

## 3. Acceptance Criteria
1. `TrackerService` корректно находит новые вышедшие серии и обновляет как Google Таблицу, так и записи в БД.
2. При отсутствии Google Таблицы `TrackerService` без сбоев выполняет проверку по записям из БД.
3. `SearchService` находит тайтлы по запросам с «е» и «ё», при вводе спецсимволов не падает, а переключается на fallback.
4. `DigestService` генерирует валидную Telegram HTML разметку со ссылками.
5. Unit-тесты покрывают `tracker`, `search` и `digest` в `tests/test_tracker.py`, `tests/test_search.py`, `tests/test_digest.py`.
6. `pytest`, `ruff` и `mypy` проходят со 100% успехом.
