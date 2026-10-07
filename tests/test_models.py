"""
Тесты для app/db/models.py — SQLAlchemy 2.0 модели данных.

Стратегия: TDD Red Phase — проверяем структуру таблиц и дефолты.
"""
from __future__ import annotations

import pytest


class TestUserModel:
    """Тесты модели User."""

    def test_user_has_required_columns(self) -> None:
        """User должен иметь все обязательные колонки."""
        from app.db.models import User

        columns = {c.name for c in User.__table__.columns}
        required = {
            "telegram_id", "username", "timezone",
            "delivery_time", "is_active", "created_at",
        }
        assert required.issubset(columns), (
            f"Отсутствуют колонки: {required - columns}"
        )

    def test_user_telegram_id_is_primary_key(self) -> None:
        """telegram_id должен быть Primary Key."""
        from app.db.models import User

        pk_cols = {c.name for c in User.__table__.primary_key}
        assert "telegram_id" in pk_cols

    def test_user_default_timezone(self) -> None:
        """Дефолтная таймзона — 'Europe/Moscow'."""
        from app.db.models import User

        col = User.__table__.columns["timezone"]
        assert col.default is not None or col.server_default is not None or str(col.type) is not None
        # Проверяем через инициализацию объекта
        user = User(telegram_id=1)  # type: ignore[call-arg]
        assert user.timezone == "Europe/Moscow"

    def test_user_default_is_active(self) -> None:
        """Дефолтное значение is_active — True."""
        from app.db.models import User

        user = User(telegram_id=1)  # type: ignore[call-arg]
        assert user.is_active is True

    def test_user_table_name(self) -> None:
        """Таблица должна называться 'users'."""
        from app.db.models import User

        assert User.__tablename__ == "users"


class TestGoogleCredentialsModel:
    """Тесты модели GoogleCredentials."""

    def test_google_credentials_has_required_columns(self) -> None:
        """GoogleCredentials должен иметь все необходимые колонки."""
        from app.db.models import GoogleCredentials

        columns = {c.name for c in GoogleCredentials.__table__.columns}
        required = {
            "id", "user_id", "encrypted_refresh_token",
            "token_uri", "client_id", "client_secret",
            "scopes", "spreadsheet_id",
        }
        assert required.issubset(columns), (
            f"Отсутствуют колонки: {required - columns}"
        )

    def test_google_credentials_table_name(self) -> None:
        """Таблица должна называться 'google_credentials'."""
        from app.db.models import GoogleCredentials

        assert GoogleCredentials.__tablename__ == "google_credentials"

    def test_google_credentials_spreadsheet_id_nullable(self) -> None:
        """spreadsheet_id должен быть nullable (пользователь мог не настроить)."""
        from app.db.models import GoogleCredentials

        col = GoogleCredentials.__table__.columns["spreadsheet_id"]
        assert col.nullable is True


class TestTrackedTitleModel:
    """Тесты модели TrackedTitle."""

    def test_tracked_title_has_required_columns(self) -> None:
        """TrackedTitle должен иметь все обязательные колонки."""
        from app.db.models import TrackedTitle

        columns = {c.name for c in TrackedTitle.__table__.columns}
        required = {
            "id", "user_id", "shiki_id", "title_name_ru",
            "status_in_table", "row_index", "last_episodes_aired",
            "total_episodes", "updated_at",
        }
        assert required.issubset(columns), (
            f"Отсутствуют колонки: {required - columns}"
        )

    def test_tracked_title_default_episodes_aired(self) -> None:
        """last_episodes_aired по умолчанию должен быть 0."""
        from app.db.models import TrackedTitle

        title = TrackedTitle(  # type: ignore[call-arg]
            user_id=1,
            shiki_id=123,
            title_name_ru="Test",
            status_in_table="В работе",
        )
        assert title.last_episodes_aired == 0

    def test_tracked_title_table_name(self) -> None:
        """Таблица должна называться 'tracked_titles'."""
        from app.db.models import TrackedTitle

        assert TrackedTitle.__tablename__ == "tracked_titles"

    def test_tracked_title_row_index_nullable(self) -> None:
        """row_index должен быть nullable."""
        from app.db.models import TrackedTitle

        col = TrackedTitle.__table__.columns["row_index"]
        assert col.nullable is True

    def test_tracked_title_total_episodes_nullable(self) -> None:
        """total_episodes должен быть nullable (может быть неизвестен)."""
        from app.db.models import TrackedTitle

        col = TrackedTitle.__table__.columns["total_episodes"]
        assert col.nullable is True
