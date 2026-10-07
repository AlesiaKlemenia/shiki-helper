"""
Тесты для app/config.py — проверка наличия всех обязательных полей Settings.

Стратегия: TDD Red Phase — тесты написаны ДО реализации.
"""
from __future__ import annotations

import os

import pytest


class TestSettingsFields:
    """Проверяем, что класс Settings содержит все необходимые поля."""

    def test_settings_has_bot_token(self) -> None:
        """BOT_TOKEN — обязательное поле для подключения к Telegram API."""
        from app.config import Settings

        assert hasattr(Settings.model_fields, "bot_token"), (
            "Settings должен содержать поле 'bot_token'"
        )

    def test_settings_has_database_url(self) -> None:
        """DATABASE_URL — строка подключения к PostgreSQL или SQLite."""
        from app.config import Settings

        assert hasattr(Settings.model_fields, "database_url"), (
            "Settings должен содержать поле 'database_url'"
        )

    def test_settings_has_redis_url(self) -> None:
        """REDIS_URL — опциональная строка для Redis FSM Storage."""
        from app.config import Settings

        field = Settings.model_fields.get("redis_url")
        assert field is not None, "Settings должен содержать поле 'redis_url'"
        # Redis — опциональный (graceful degradation)
        assert not field.is_required(), (
            "redis_url должен быть опциональным полем"
        )

    def test_settings_has_encryption_key(self) -> None:
        """ENCRYPTION_KEY — 32-байтный Fernet-ключ для шифрования OAuth токенов."""
        from app.config import Settings

        assert hasattr(Settings.model_fields, "encryption_key"), (
            "Settings должен содержать поле 'encryption_key'"
        )

    def test_settings_has_google_credentials(self) -> None:
        """GOOGLE_CLIENT_ID и GOOGLE_CLIENT_SECRET — для OAuth с Google."""
        from app.config import Settings

        assert hasattr(Settings.model_fields, "google_client_id"), (
            "Settings должен содержать поле 'google_client_id'"
        )
        assert hasattr(Settings.model_fields, "google_client_secret"), (
            "Settings должен содержать поле 'google_client_secret'"
        )

    def test_settings_has_admin_telegram_id(self) -> None:
        """ADMIN_TELEGRAM_ID — ID администратора для уведомлений о сбоях."""
        from app.config import Settings

        assert hasattr(Settings.model_fields, "admin_telegram_id"), (
            "Settings должен содержать поле 'admin_telegram_id'"
        )

    def test_settings_loads_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Settings корректно читает значения из переменных окружения."""
        monkeypatch.setenv("BOT_TOKEN", "test:token123")
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
        monkeypatch.setenv(
            "ENCRYPTION_KEY",
            "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ=",  # 32-byte base64
        )
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test_client_id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test_client_secret")
        monkeypatch.setenv("ADMIN_TELEGRAM_ID", "123456789")

        # Удаляем кэш модуля для перечитки env
        import importlib
        import sys

        if "app.config" in sys.modules:
            importlib.reload(sys.modules["app.config"])

        from app.config import Settings

        settings = Settings()  # type: ignore[call-arg]

        assert settings.bot_token == "test:token123"
        assert settings.database_url == "sqlite+aiosqlite:///./test.db"
        assert settings.admin_telegram_id == 123456789

    def test_settings_redis_url_defaults_to_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Если REDIS_URL не задан, redis_url == None (graceful degradation)."""
        monkeypatch.setenv("BOT_TOKEN", "test:token123")
        monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
        monkeypatch.setenv(
            "ENCRYPTION_KEY",
            "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ=",
        )
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "csec")
        monkeypatch.setenv("ADMIN_TELEGRAM_ID", "1")
        monkeypatch.delenv("REDIS_URL", raising=False)

        import importlib
        import sys

        if "app.config" in sys.modules:
            importlib.reload(sys.modules["app.config"])

        from app.config import Settings

        settings = Settings()  # type: ignore[call-arg]
        assert settings.redis_url is None
