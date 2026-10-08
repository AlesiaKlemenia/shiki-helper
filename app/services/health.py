"""HTTP Healthcheck сервер на базе aiohttp.web для Render и систем мониторинга."""
from __future__ import annotations

import logging
import time
from typing import Optional

from aiohttp import web

logger = logging.getLogger(__name__)


def create_health_app(bot_username: str = "shiki_helper_bot") -> web.Application:
    """Создаёт aiohttp.web приложение с эндпоинтом /health."""
    start_time = time.time()
    app = web.Application()

    async def health_handler(request: web.Request) -> web.Response:
        uptime = round(time.time() - start_time, 2)
        return web.json_response(
            {
                "status": "ok",
                "bot": bot_username,
                "uptime_seconds": uptime,
            }
        )

    app.router.add_get("/health", health_handler)
    return app


class HealthcheckServer:
    """Фоновый HTTP веб-сервер для обработки ping-запросов /health."""

    def __init__(self, port: int, bot_username: str = "shiki_helper_bot", host: str = "0.0.0.0") -> None:
        self.port = port
        self.host = host
        self.bot_username = bot_username
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None

    async def start(self) -> None:
        """Запускает HTTP-сервер на указанном порту."""
        app = create_health_app(bot_username=self.bot_username)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()
        logger.info("Healthcheck HTTP сервер запущен на http://%s:%d/health", self.host, self.port)

    async def stop(self) -> None:
        """Останавливает HTTP-сервер и освобождает ресурсы."""
        if self.runner is not None:
            await self.runner.cleanup()
            self.runner = None
            self.site = None
            logger.info("Healthcheck HTTP сервер остановлен.")
