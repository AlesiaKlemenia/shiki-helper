"""Тесты для app/clients/shikimori.py — клиент Shikimori GraphQL API и механизмы Resilience.

Стратегия: TDD Red Phase — тесты написаны ДО реализации.
Используется библиотека respx для точного мокирования HTTP-запросов httpx.
"""
from __future__ import annotations

import httpx
import pytest
import respx

from app.clients.shikimori import AnimeInfo, ShikimoriAPIError, ShikimoriGraphQLClient


GRAPHQL_URL = "https://shikimori.io/api/graphql"


class TestAnimeInfoModel:
    """Тестирование структуры и десериализации модели AnimeInfo."""

    def test_anime_info_instantiation(self) -> None:
        anime = AnimeInfo(
            id=123,
            name="Sousou no Frieren",
            russian="Провожающая в последний путь Фрирен",
            status="released",
            episodes=28,
            episodes_aired=28,
            url="https://shikimori.one/animes/123-sousou-no-frieren",
        )
        assert anime.id == 123
        assert anime.name == "Sousou no Frieren"
        assert anime.russian == "Провожающая в последний путь Фрирен"
        assert anime.episodes_aired == 28

    def test_anime_info_optional_russian_title(self) -> None:
        anime = AnimeInfo(
            id=456,
            name="Unknown Title",
            russian=None,
            status="anons",
            episodes=12,
            episodes_aired=0,
            url="https://shikimori.one/animes/456",
        )
        assert anime.russian is None


class TestShikimoriGraphQLClient:
    """Тестирование запросов и сценариев устойчивости (Resilience)."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_animes_success(self) -> None:
        """Успешное получение списка аниме по списку ID."""
        mock_payload = {
            "data": {
                "animes": [
                    {
                        "id": 1,
                        "name": "Cowboy Bebop",
                        "russian": "Ковбой Бибоп",
                        "status": "released",
                        "episodes": 26,
                        "episodesAired": 26,
                        "url": "https://shikimori.one/animes/1-cowboy-bebop",
                    }
                ]
            }
        }
        respx.post(GRAPHQL_URL).mock(return_value=httpx.Response(200, json=mock_payload))

        client = ShikimoriGraphQLClient(user_agent="Shiki-Test-Bot/1.0")
        results = await client.fetch_animes_by_ids([1])

        assert len(results) == 1
        assert results[0].id == 1
        assert results[0].name == "Cowboy Bebop"
        assert results[0].episodes_aired == 26
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_user_agent_header_included(self) -> None:
        """Заголовок User-Agent обязательно передаётся в каждом запросе."""
        custom_ua = "Custom-Shiki-Agent/2.0"
        route = respx.post(GRAPHQL_URL).mock(
            return_value=httpx.Response(200, json={"data": {"animes": []}})
        )

        client = ShikimoriGraphQLClient(user_agent=custom_ua)
        await client.fetch_animes_by_ids([10])

        assert route.called
        assert route.calls.last.request.headers.get("User-Agent") == custom_ua
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_auth_token_header_included(self) -> None:
        """Передача опционального OAuth-токена в заголовке Authorization."""
        route = respx.post(GRAPHQL_URL).mock(
            return_value=httpx.Response(200, json={"data": {"animes": []}})
        )

        client = ShikimoriGraphQLClient(access_token="secret_oauth_token")
        await client.fetch_animes_by_ids([10])

        assert route.called
        assert route.calls.last.request.headers.get("Authorization") == "Bearer secret_oauth_token"
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_auth_token_fallback_on_401(self) -> None:
        """При получении HTTP 401 клиент повторяет запрос в публичном режиме без Bearer токена."""
        mock_payload = {
            "data": {
                "animes": [
                    {
                        "id": 2,
                        "name": "Trigun",
                        "russian": "Триган",
                        "status": "released",
                        "episodes": 26,
                        "episodesAired": 26,
                        "url": "https://shikimori.one/animes/2-trigun",
                    }
                ]
            }
        }
        # 1-я попытка с токеном -> 401 Unauthorized
        # 2-я попытка без токена -> 200 OK
        route = respx.post(GRAPHQL_URL)
        route.side_effect = [
            httpx.Response(401, json={"error": "invalid_token"}),
            httpx.Response(200, json=mock_payload),
        ]

        client = ShikimoriGraphQLClient(access_token="expired_token")
        results = await client.fetch_animes_by_ids([2])

        assert len(results) == 1
        assert results[0].id == 2
        assert route.call_count == 2
        # Второй запрос должен быть уже без Authorization заголовка
        assert "Authorization" not in route.calls.last.request.headers
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_batching_chunks_of_50(self) -> None:
        """Список из >50 ID (>50) разбивается на чанки по 50 тайтлов."""
        # 75 ID должно дать ровно 2 POST-запроса: 50 и 25
        ids = list(range(1, 76))
        route = respx.post(GRAPHQL_URL).mock(
            return_value=httpx.Response(200, json={"data": {"animes": []}})
        )

        client = ShikimoriGraphQLClient()
        await client.fetch_animes_by_ids(ids)

        assert route.call_count == 2
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_retry_on_429_too_many_requests(self) -> None:
        """Retry с backoff при HTTP 429 и успешный ответ со 2-й попытки."""
        mock_payload = {
            "data": {
                "animes": [
                    {
                        "id": 5,
                        "name": "Bleach",
                        "russian": "Блич",
                        "status": "released",
                        "episodes": 366,
                        "episodesAired": 366,
                        "url": "https://shikimori.one/animes/5-bleach",
                    }
                ]
            }
        }
        route = respx.post(GRAPHQL_URL)
        route.side_effect = [
            httpx.Response(429, headers={"Retry-After": "0.1"}),
            httpx.Response(200, json=mock_payload),
        ]

        client = ShikimoriGraphQLClient(base_retry_delay=0.01)
        results = await client.fetch_animes_by_ids([5])

        assert len(results) == 1
        assert results[0].id == 5
        assert route.call_count == 2
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_retry_on_5xx_server_error(self) -> None:
        """Retry при HTTP 502/503/504 ошибках сервера."""
        mock_payload = {
            "data": {
                "animes": [
                    {
                        "id": 6,
                        "name": "Naruto",
                        "russian": "Наруто",
                        "status": "released",
                        "episodes": 220,
                        "episodesAired": 220,
                        "url": "https://shikimori.one/animes/6-naruto",
                    }
                ]
            }
        }
        route = respx.post(GRAPHQL_URL)
        route.side_effect = [
            httpx.Response(502, text="Bad Gateway"),
            httpx.Response(503, text="Service Unavailable"),
            httpx.Response(200, json=mock_payload),
        ]

        client = ShikimoriGraphQLClient(base_retry_delay=0.01, max_retries=3)
        results = await client.fetch_animes_by_ids([6])

        assert len(results) == 1
        assert results[0].id == 6
        assert route.call_count == 3
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_retry_on_empty_response(self) -> None:
        """Retry при пустом ответе или отсутствии data.animes."""
        mock_payload = {
            "data": {
                "animes": [
                    {
                        "id": 7,
                        "name": "One Piece",
                        "russian": "Ван Пис",
                        "status": "ongoing",
                        "episodes": 0,
                        "episodesAired": 1100,
                        "url": "https://shikimori.one/animes/7-one-piece",
                    }
                ]
            }
        }
        route = respx.post(GRAPHQL_URL)
        route.side_effect = [
            httpx.Response(200, json={}),  # Пустые данные
            httpx.Response(200, json=mock_payload),
        ]

        client = ShikimoriGraphQLClient(base_retry_delay=0.01)
        results = await client.fetch_animes_by_ids([7])

        assert len(results) == 1
        assert results[0].id == 7
        assert route.call_count == 2
        await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_shikimori_api_error_after_max_retries(self) -> None:
        """Выбрасывает ShikimoriAPIError при исчерпании всех повторных попыток."""
        route = respx.post(GRAPHQL_URL).mock(return_value=httpx.Response(500, text="Internal Server Error"))

        client = ShikimoriGraphQLClient(base_retry_delay=0.01, max_retries=2)

        with pytest.raises(ShikimoriAPIError, match="превышено максимальное число попыток"):
            await client.fetch_animes_by_ids([100])

        assert route.call_count == 3  # Начальный запрос + 2 повтора
        await client.close()
