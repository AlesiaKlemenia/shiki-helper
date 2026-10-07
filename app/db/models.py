"""
SQLAlchemy 2.0 модели базы данных Shiki-Helper.

Модели:
    - User: пользователь бота с настройками таймзоны и времени рассылки.
    - GoogleCredentials: зашифрованные OAuth-токены и настройки Google Sheets.
    - TrackedTitle: отслеживаемый аниме-тайтл с состоянием серий.

Использование:
    from app.db.models import Base, User, GoogleCredentials, TrackedTitle
    # Для создания таблиц используйте Alembic миграции.
"""
from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Базовый класс для всех SQLAlchemy-моделей."""

    pass


class User(Base):
    """Пользователь Telegram-бота.

    Хранит настройки персональной рассылки и статус активности.
    Primary Key — Telegram ID пользователя.
    """

    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        comment="Уникальный Telegram ID пользователя",
    )
    username: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="Имя пользователя в Telegram (без @)",
    )
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="Europe/Moscow",
        comment="Часовой пояс для рассылки дайджеста (IANA формат)",
    )
    delivery_time: Mapped[Optional[datetime.time]] = mapped_column(
        Time,
        nullable=True,
        default=datetime.time(19, 0, 0),
        comment="Время ежедневной рассылки дайджеста",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Активен ли пользователь (может отписаться от рассылки)",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        comment="Дата регистрации (UTC)",
    )

    # Связи
    google_credentials: Mapped[Optional["GoogleCredentials"]] = relationship(
        "GoogleCredentials",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    tracked_titles: Mapped[list["TrackedTitle"]] = relationship(
        "TrackedTitle",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<User id={self.telegram_id} "
            f"username={self.username!r} "
            f"tz={self.timezone!r}>"
        )


class GoogleCredentials(Base):
    """Зашифрованные OAuth-учётные данные Google пользователя.

    refresh_token хранится в зашифрованном виде через Fernet.
    Привязан к одному пользователю (OneToOne).
    """

    __tablename__ = "google_credentials"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="FK на users.telegram_id",
    )
    encrypted_refresh_token: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Зашифрованный Fernet refresh_token Google OAuth",
    )
    token_uri: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        default="https://oauth2.googleapis.com/token",
        comment="URL для обновления access_token",
    )
    client_id: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        comment="Google OAuth Client ID",
    )
    client_secret: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        comment="Google OAuth Client Secret",
    )
    scopes: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="JSON-список запрошенных OAuth scopes",
    )
    spreadsheet_id: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        comment="ID Google Таблицы (из URL: /spreadsheets/d/<ID>/)",
    )

    # Связи
    user: Mapped["User"] = relationship(
        "User",
        back_populates="google_credentials",
    )

    def __repr__(self) -> str:
        return (
            f"<GoogleCredentials user_id={self.user_id} "
            f"spreadsheet_id={self.spreadsheet_id!r}>"
        )


class TrackedTitle(Base):
    """Отслеживаемый аниме-тайтл пользователя.

    Хранит состояние: сколько серий вышло на момент последней проверки.
    Используется для определения дельты (новых серий) при следующей проверке.
    """

    __tablename__ = "tracked_titles"

    __table_args__ = (
        Index("ix_tracked_titles_user_id", "user_id"),
        Index("ix_tracked_titles_shiki_id", "shiki_id"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="CASCADE"),
        nullable=False,
        comment="FK на users.telegram_id",
    )
    shiki_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="ID тайтла на Shikimori",
    )
    title_name_ru: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="Русское название тайтла (из колонки A Google Таблицы)",
    )
    status_in_table: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Статус из колонки C: 'В работе', 'В планах', 'Анонс'",
    )
    row_index: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Индекс строки в Google Таблице для точечного обновления",
    )
    last_episodes_aired: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Последнее зафиксированное количество вышедших серий",
    )
    total_episodes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Всего серий по плану (None если неизвестно)",
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
        comment="Дата последнего обновления записи (UTC)",
    )

    # Связи
    user: Mapped["User"] = relationship(
        "User",
        back_populates="tracked_titles",
    )

    def __repr__(self) -> str:
        return (
            f"<TrackedTitle id={self.id} "
            f"shiki_id={self.shiki_id} "
            f"aired={self.last_episodes_aired}/{self.total_episodes}>"
        )
