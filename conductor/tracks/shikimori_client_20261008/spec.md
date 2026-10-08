# Specification: Клиент Shikimori GraphQL API и Resilience

**Track ID:** `shikimori_client_20261008`
**Type:** Feature
**Status:** Draft

---

## 1. Overview
Реализация асинхронного клиента к официальному GraphQL API Shikimori (`https://shikimori.one/api/graphql`) для получения актуальных данных об эпизодах аниме. Клиент обеспечивает эффективный пакетный сбор информации без жесткого внутреннего лимитера частоты, с акцентом на автоматическую обработку rate limit (HTTP 429) и временных сбоев сервера (HTTP 502/503/504) через стратегию Exponential Backoff с джиттером.

---

## 2. Requirements & Technical Architecture

### 2.1. Конфигурация и заголовки
- **Эндпоинт:** `https://shikimori.one/api/graphql`
- **User-Agent:** Обязательный кастомный заголовок (по умолчанию `Shiki-Helper-Bot/1.0`), настраиваемый через инициализатор клиента.
- **Авторизация:** Поддержка опционального OAuth Bearer токена (`Authorization: Bearer <token>`). Если токен не передан — запросы идут в публичном гостевом режиме. При получении HTTP 401 — логирование предупреждения и прозрачный fallback на публичный режим.

### 2.2. Запрос данных (GraphQL Payload)
Точечный GraphQL-запрос полей, необходимых для трекинга серий:
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

### 2.3. Пакетная выгрузка и чанкование
- Метод `fetch_animes_by_ids(ids: list[int]) -> list[AnimeInfo]`:
  - Автоматически разбивает переданный список `ids` на пачки максимум по 50 тайтлов (ограничение API Shikimori).
  - Формирует строку `ids: "1,2,3,..."` для аргумента GraphQL.
  - Собирает и объединяет результаты в единый список моделей данных.

### 2.4. Модели данных (DTO)
- `AnimeInfo` (Pydantic модель или dataclass):
  - `id: int`
  - `name: str` (оригинальное название)
  - `russian: Optional[str]` (русское название)
  - `status: str` (released, ongoing, anons)
  - `episodes: int` (общее запланированное число серий)
  - `episodes_aired: int` (вышедшее число серий)
  - `url: str` (ссылка на страницу на Shikimori)

### 2.5. Стратегия отказоустойчивости (Resilience)
- **Rate Limiting Policy:** Без жесткого локального троттлинга; клиент отправляет запросы свободно, опираясь на обработчик ошибок.
- **Exponential Backoff с Jitter:**
  - Ошибки, подлежащие retry: HTTP 429 (Too Many Requests), HTTP 502, 503, 504, сетевые тайм-ауты (`httpx.TimeoutException`, `httpx.NetworkError`).
  - Формула паузы: `delay = base_delay * (2 ** attempt) + random_jitter`.
  - Учет заголовка `Retry-After` при HTTP 429: если заголовок присутствует, ожидание устанавливается строго по значению сервера.
  - Количество повторных попыток по умолчанию: до 3 раз.
- **Пустой ответ:** При пустом теле или отсутствии ключа `data.animes` производится повторная попытка.

---

## 3. Acceptance Criteria
1. Модуль `app/clients/shikimori.py` содержит класс `ShikimoriGraphQLClient`.
2. Запросы корректно сериализуют GraphQL query и десериализуют ответ в список объектов `AnimeInfo`.
3. Список из >50 идентификаторов корректно разбивается на чанки по 50 и склеивается обратно.
4. При статусах 429 и 5xx клиент делает повторные попытки с растущей задержкой и успешно возвращает результат при восстановлении.
5. При фатальной ошибке после исчерпания попыток выбрасывается специфичное исключение `ShikimoriAPIError`.
6. Покрытие тестами через `pytest` и `respx` составляет 100% для всех ветвей логики клиента.
7. `ruff check` и `mypy` не выдают ошибок.
