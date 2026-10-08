"""Unit-тесты для HTTP Healthcheck сервера (aiohttp.web).

Стратегия: TDD Red Phase.
"""
from __future__ import annotations

import pytest
from aiohttp.test_utils import TestClient, TestServer

from app.services.health import HealthcheckServer, create_health_app


class TestHealthcheckServer:
    """Тестирование эндпоинта /health и жизненного цикла сервера."""

    @pytest.mark.asyncio
    async def test_get_health_endpoint(self) -> None:
        app = create_health_app(bot_username="shiki_helper_bot")
        server = TestServer(app)
        client = TestClient(server)
        await client.start_server()
        try:
            resp = await client.get("/health")
            assert resp.status == 200

            data = await resp.json()
            assert data["status"] == "ok"
            assert data["bot"] == "shiki_helper_bot"
            assert "uptime_seconds" in data
            assert isinstance(data["uptime_seconds"], (int, float))
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_server_start_and_stop_lifecycle(self) -> None:
        server = HealthcheckServer(port=9876, bot_username="shiki_helper_bot")
        try:
            await server.start()
            assert server.runner is not None
        finally:
            await server.stop()
            assert server.runner is None
