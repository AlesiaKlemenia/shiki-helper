"""
Конфигурация приложения через Pydantic BaseSettings.

Все настройки читаются из переменных окружения (файл .env или системные env).
При старте приложения создаётся единственный экземпляр `settings`.
"""
from __future__ import annotations

from typing import Optional, cast

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения Shiki-Helper.

    Читает переменные окружения и .env файл. Все секретные поля
    должны задаваться только через окружение, никогда не хардкодиться.

    Args:
        bot_token: Токен Telegram-бота от @BotFather.
        database_url: Строка подключения к БД (asyncpg или aiosqlite).
        redis_url: URL Redis для FSM Storage. None → MemoryStorage fallback.
        encryption_key: Fernet-ключ (base64) для шифрования OAuth-токенов.
        google_client_id: OAuth Client ID из Google Cloud Console.
        google_client_secret: OAuth Client Secret из Google Cloud Console.
        admin_telegram_id: Telegram ID администратора для уведомлений.
        log_level: Уровень логирования (DEBUG/INFO/WARNING/ERROR).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Telegram ---
    bot_token: str = Field(
        ...,
        description="Токен Telegram-бота от @BotFather",
    )

    # --- База данных ---
    database_url: str = Field(
        ...,
        description=(
            "Строка подключения к БД. "
            "Примеры: 'postgresql+asyncpg://user:pass@host/db' "
            "или 'sqlite+aiosqlite:///./shiki.db'"
        ),
    )

    # --- Redis (опциональный) ---
    redis_url: Optional[str] = Field(
        default=None,
        description=(
            "URL подключения к Redis. "
            "Если не задан — FSM переключится на MemoryStorage. "
            "Пример: 'redis://localhost:6379/0' или 'rediss://...upstash.io:6379'"
        ),
    )

    # --- Безопасность / Шифрование ---
    encryption_key: str = Field(
        ...,
        description=(
            "Fernet-ключ в формате base64 (32 байта). "
            "Генерация: from cryptography.fernet import Fernet; Fernet.generate_key()"
        ),
    )

    # --- Google OAuth ---
    google_client_id: str = Field(
        ...,
        description="OAuth 2.0 Client ID из Google Cloud Console",
    )
    google_client_secret: str = Field(
        ...,
        description="OAuth 2.0 Client Secret из Google Cloud Console",
    )

    # --- Администрирование ---
    admin_telegram_id: int = Field(
        ...,
        description="Telegram ID администратора для получения уведомлений о сбоях",
    )
    sandbox_user_ids: list[int] = Field(
        default_factory=list,
        description="Список Telegram ID пользователей, для которых включен изолированный режим sandbox",
    )

    # --- Логирование и Сервер ---
    log_level: str = Field(
        default="INFO",
        description="Уровень логирования: DEBUG, INFO, WARNING, ERROR",
    )
    port: int = Field(
        default=8000,
        alias="PORT",
        description="Порт для HTTP healthcheck сервера (на Render передается через $PORT)",
    )


def get_settings() -> Settings:
    """Возвращает экземпляр Settings, читая переменные окружения."""
    return Settings()  # type: ignore[call-arg]


class _LazySettings:
    """Ленивая обертка над Settings, чтобы импорт app.config не падал при пустом .env в тестах."""

    def __init__(self) -> None:
        self._settings: Optional[Settings] = None

    def __getattr__(self, name: str) -> object:
        if self._settings is None:
            self._settings = get_settings()
        return getattr(self._settings, name)


settings: Settings = cast(Settings, _LazySettings())


