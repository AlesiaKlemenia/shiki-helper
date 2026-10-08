"""Асинхронный клиент для взаимодействия с Shikimori GraphQL API.

Особенности:
- Обязательный заголовок User-Agent.
- Поддержка опциональной авторизации (Bearer-токен) с авто-fallback на публичный режим при 401.
- Пакетное получение тайтлов (батчинг по 50 записей).
- Стратегия Resilience: Exponential Backoff с джиттером при 429 (Too Many Requests),
  502/503/504 ошибках сервера и временных сетевых сбоях.
"""
from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

GRAPHQL_URL = "https://shikimori.one/api/graphql"
DEFAULT_USER_AGENT = "Shiki-Helper-Bot/1.0"
BATCH_SIZE = 50

ANIMES_QUERY = """
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
"""


class ShikimoriAPIError(Exception):
    """Базовое исключение для ошибок взаимодействия с API Shikimori."""

    pass


@dataclass(frozen=True, slots=True)
class AnimeInfo:
    """DTO с информацией о тайтле из Shikimori API."""

    id: int
    name: str
    russian: Optional[str]
    status: str
    episodes: int
    episodes_aired: int
    url: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnimeInfo:
        """Создает экземпляр AnimeInfo из словаря ответа GraphQL."""
        return cls(
            id=int(data["id"]),
            name=str(data.get("name", "")),
            russian=data.get("russian") or None,
            status=str(data.get("status", "")),
            episodes=int(data.get("episodes", 0)),
            episodes_aired=int(data.get("episodesAired", 0)),
            url=str(data.get("url", "")),
        )


class ShikimoriGraphQLClient:
    """Асинхронный GraphQL-клиент к Shikimori."""

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        access_token: Optional[str] = None,
        base_retry_delay: float = 1.0,
        max_retries: int = 3,
        timeout: float = 15.0,
    ) -> None:
        self.user_agent = user_agent
        self.access_token = access_token
        self.base_retry_delay = base_retry_delay
        self.max_retries = max_retries
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        """Закрывает базовую HTTP-сессию."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> ShikimoriGraphQLClient:
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> None:
        await self.close()

    async def _send_graphql_query(
        self, query: str, variables: dict[str, Any]
    ) -> dict[str, Any]:
        """Отправляет GraphQL-запрос с автоматическим механизмом повторов (Exponential Backoff)."""
        client = await self._get_client()
        attempt = 0
        payload = {"query": query, "variables": variables}

        while attempt <= self.max_retries:
            headers = self._get_headers()
            try:
                response = await client.post(GRAPHQL_URL, json=payload, headers=headers)

                # Обработка истекшего токена авторизации (HTTP 401)
                if response.status_code == 401 and self.access_token is not None:
                    logger.warning(
                        "Получен HTTP 401 Unauthorized от Shikimori. "
                        "Сбрасываем access_token и переключаемся в публичный режим."
                    )
                    self.access_token = None
                    attempt += 1
                    continue

                # Rate Limit (HTTP 429) или ошибки сервера (5xx)
                if response.status_code == 429 or response.status_code in {502, 503, 504}:
                    retry_after_header = response.headers.get("Retry-After")
                    if retry_after_header is not None:
                        try:
                            delay = float(retry_after_header)
                        except ValueError:
                            delay = self._calculate_backoff_delay(attempt)
                    else:
                        delay = self._calculate_backoff_delay(attempt)

                    logger.warning(
                        "Shikimori вернул статус %d (попытка %d/%d). Ожидание %.2f с...",
                        response.status_code,
                        attempt + 1,
                        self.max_retries,
                        delay,
                    )
                    attempt += 1
                    if attempt > self.max_retries:
                        break
                    await asyncio.sleep(delay)
                    continue

                response.raise_for_status()

                data = response.json()
                if not data or "data" not in data or "animes" not in data.get("data", {}):
                    # Пустой ответ или поврежденная структура GraphQL
                    delay = self._calculate_backoff_delay(attempt)
                    logger.warning(
                        "Пустой или некорректный ответ от Shikimori GraphQL (попытка %d/%d). "
                        "Повтор через %.2f с...",
                        attempt + 1,
                        self.max_retries,
                        delay,
                    )
                    attempt += 1
                    if attempt > self.max_retries:
                        break
                    await asyncio.sleep(delay)
                    continue

                return data

            except (httpx.TimeoutException, httpx.NetworkError) as net_err:
                delay = self._calculate_backoff_delay(attempt)
                logger.warning(
                    "Сетевая ошибка при обращении к Shikimori: %s (попытка %d/%d). Ожидание %.2f с...",
                    net_err,
                    attempt + 1,
                    self.max_retries,
                    delay,
                )
                attempt += 1
                if attempt > self.max_retries:
                    break
                await asyncio.sleep(delay)
            except httpx.HTTPStatusError as http_err:
                logger.error("Критическая HTTP ошибка Shikimori: %s", http_err)
                attempt += 1
                if attempt > self.max_retries:
                    break
                delay = self._calculate_backoff_delay(attempt)
                await asyncio.sleep(delay)

        raise ShikimoriAPIError(
            f"Не удалось выполнить запрос к Shikimori API: превышено максимальное число попыток ({self.max_retries})."
        )

    def _calculate_backoff_delay(self, attempt: int) -> float:
        """Вычисляет паузу: base_delay * (2 ** attempt) + random jitter."""
        backoff = self.base_retry_delay * (2**attempt)
        jitter = random.uniform(0.05, 0.25)
        return backoff + jitter

    async def fetch_animes_by_ids(self, ids: list[int]) -> list[AnimeInfo]:
        """Пакетно запрашивает данные по списку ID тайтлов с чанкованием по 50 элементов.

        Args:
            ids: Список идентификаторов Shikimori.

        Returns:
            Список объектов AnimeInfo.
        """
        if not ids:
            return []

        results: list[AnimeInfo] = []

        # Разбиение на чанки по 50 элементов
        for i in range(0, len(ids), BATCH_SIZE):
            chunk = ids[i : i + BATCH_SIZE]
            ids_str = ",".join(str(item_id) for item_id in chunk)
            variables = {"ids": ids_str, "limit": len(chunk)}

            response_data = await self._send_graphql_query(ANIMES_QUERY, variables)
            animes_raw = response_data.get("data", {}).get("animes", [])

            for item in animes_raw:
                results.append(AnimeInfo.from_dict(item))

        return results
