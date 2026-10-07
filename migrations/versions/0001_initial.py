"""Initial database schema: users, google_credentials, tracked_titles.

Revision ID: 0001_initial
Revises: 
Create Date: 2026-10-07 19:35:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply migrations: create users, google_credentials, tracked_titles tables."""
    # Table: users
    op.create_table(
        "users",
        sa.Column(
            "telegram_id",
            sa.BigInteger(),
            nullable=False,
            comment="Уникальный Telegram ID пользователя",
        ),
        sa.Column(
            "username",
            sa.String(length=64),
            nullable=True,
            comment="Имя пользователя в Telegram (без @)",
        ),
        sa.Column(
            "timezone",
            sa.String(length=64),
            nullable=False,
            server_default="Europe/Moscow",
            comment="Часовой пояс для рассылки дайджеста (IANA формат)",
        ),
        sa.Column(
            "delivery_time",
            sa.Time(),
            nullable=True,
            comment="Время ежедневной рассылки дайджеста",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
            comment="Активен ли пользователь (может отписаться от рассылки)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Дата регистрации (UTC)",
        ),
        sa.PrimaryKeyConstraint("telegram_id"),
    )

    # Table: google_credentials
    op.create_table(
        "google_credentials",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            nullable=False,
            comment="FK на users.telegram_id",
        ),
        sa.Column(
            "encrypted_refresh_token",
            sa.Text(),
            nullable=False,
            comment="Зашифрованный Fernet refresh_token Google OAuth",
        ),
        sa.Column(
            "token_uri",
            sa.String(length=512),
            nullable=False,
            server_default="https://oauth2.googleapis.com/token",
            comment="URL для обновления access_token",
        ),
        sa.Column(
            "client_id",
            sa.String(length=256),
            nullable=False,
            comment="Google OAuth Client ID",
        ),
        sa.Column(
            "client_secret",
            sa.String(length=256),
            nullable=False,
            comment="Google OAuth Client Secret",
        ),
        sa.Column(
            "scopes",
            sa.Text(),
            nullable=False,
            comment="JSON-список запрошенных OAuth scopes",
        ),
        sa.Column(
            "spreadsheet_id",
            sa.String(length=128),
            nullable=True,
            comment="ID Google Таблицы (из URL: /spreadsheets/d/<ID>/)",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.telegram_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    # Table: tracked_titles
    op.create_table(
        "tracked_titles",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            nullable=False,
            comment="FK на users.telegram_id",
        ),
        sa.Column(
            "shiki_id",
            sa.Integer(),
            nullable=False,
            comment="ID тайтла на Shikimori",
        ),
        sa.Column(
            "title_name_ru",
            sa.String(length=512),
            nullable=False,
            comment="Русское название тайтла (из колонки A Google Таблицы)",
        ),
        sa.Column(
            "status_in_table",
            sa.String(length=64),
            nullable=False,
            comment="Статус из колонки C: 'В работе', 'В планах', 'Анонс'",
        ),
        sa.Column(
            "row_index",
            sa.Integer(),
            nullable=True,
            comment="Индекс строки в Google Таблице для точечного обновления",
        ),
        sa.Column(
            "last_episodes_aired",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Последнее зафиксированное количество вышедших серий",
        ),
        sa.Column(
            "total_episodes",
            sa.Integer(),
            nullable=True,
            comment="Всего серий по плану (None если неизвестно)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Дата последнего обновления записи (UTC)",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.telegram_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tracked_titles_user_id",
        "tracked_titles",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_tracked_titles_shiki_id",
        "tracked_titles",
        ["shiki_id"],
        unique=False,
    )


def downgrade() -> None:
    """Revert migrations: drop tables in reverse dependency order."""
    op.drop_index("ix_tracked_titles_shiki_id", table_name="tracked_titles")
    op.drop_index("ix_tracked_titles_user_id", table_name="tracked_titles")
    op.drop_table("tracked_titles")
    op.drop_table("google_credentials")
    op.drop_table("users")
