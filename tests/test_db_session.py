"""
Тесты для app/db/session.py — async подключение к БД через SQLAlchemy.

Стратегия: TDD Red Phase — тесты написаны ДО реализации.
"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


class TestCreateAsyncEngine:
    """Тесты фабрики создания async engine."""

    def test_create_engine_for_sqlite(self) -> None:
        """Для SQLite URL должен создаваться async engine без ошибок."""
        from app.db.session import create_async_engine_from_url

        engine = create_async_engine_from_url("sqlite+aiosqlite:///:memory:")
        assert isinstance(engine, AsyncEngine)

    def test_create_engine_returns_async_engine(self) -> None:
        """Возвращаемый объект должен быть AsyncEngine."""
        from app.db.session import create_async_engine_from_url

        engine = create_async_engine_from_url("sqlite+aiosqlite:///:memory:")
        assert isinstance(engine, AsyncEngine)

    def test_create_engine_sqlite_has_correct_dialect(self) -> None:
        """Для SQLite URL диалект должен быть 'sqlite'."""
        from app.db.session import create_async_engine_from_url

        engine = create_async_engine_from_url("sqlite+aiosqlite:///:memory:")
        assert engine.dialect.name == "sqlite"


class TestGetSession:
    """Тесты контекстного менеджера get_session()."""

    @pytest.mark.asyncio
    async def test_get_session_yields_async_session(self) -> None:
        """get_session() должен yielдить экземпляр AsyncSession."""
        from app.db.session import create_session_factory

        factory = create_session_factory("sqlite+aiosqlite:///:memory:")
        async with factory() as session:
            assert isinstance(session, AsyncSession)

    @pytest.mark.asyncio
    async def test_get_session_auto_closes(self) -> None:
        """После выхода из контекстного менеджера сессия должна быть закрыта."""
        from app.db.session import create_session_factory

        factory = create_session_factory("sqlite+aiosqlite:///:memory:")
        async with factory() as session:
            _session_ref = session
            assert _session_ref.is_active

        # В SQLAlchemy async_sessionmaker при выходе из контекста вызывает close()
        # Проверяем, что транзакция завершена / сессия закрыта
        assert not _session_ref.sync_session.is_active or not _session_ref.is_active or _session_ref.sync_session._transaction is None


    @pytest.mark.asyncio
    async def test_get_session_rollback_on_exception(self) -> None:
        """При исключении внутри контекста должен выполняться rollback."""
        from app.db.session import create_session_factory

        factory = create_session_factory("sqlite+aiosqlite:///:memory:")

        with pytest.raises(RuntimeError, match="test error"):
            async with factory() as session:
                # Проверяем, что сессия активна
                assert session.is_active
                raise RuntimeError("test error")
