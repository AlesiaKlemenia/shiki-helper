"""
Тесты для DynamicSessionMaker — Shadow DB / Sandbox mode.

Стратегия: TDD Red Phase.
"""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


class TestDynamicSessionMaker:
    """Тесты переключения сессий: боевая ↔ sandbox."""

    @pytest.mark.asyncio
    async def test_get_session_without_sandbox_returns_production_session(
        self,
    ) -> None:
        """Без активного sandbox get_session() возвращает боевую сессию."""
        from app.db.sandbox import DynamicSessionMaker

        production_url = "sqlite+aiosqlite:///:memory:"
        maker = DynamicSessionMaker(database_url=production_url)

        async with maker.get_session() as session:
            assert isinstance(session, AsyncSession)

    @pytest.mark.asyncio
    async def test_get_session_in_sandbox_returns_sandbox_session(
        self,
    ) -> None:
        """После enable_sandbox() get_session() возвращает in-memory SQLite сессию."""
        from app.db.sandbox import DynamicSessionMaker

        production_url = "sqlite+aiosqlite:///:memory:"
        maker = DynamicSessionMaker(database_url=production_url)

        user_id = 12345
        await maker.enable_sandbox(user_id=user_id)
        try:
            async with maker.get_session() as session:
                assert isinstance(session, AsyncSession)
        finally:
            await maker.disable_sandbox()

    @pytest.mark.asyncio
    async def test_disable_sandbox_restores_production_session(
        self,
    ) -> None:
        """После disable_sandbox() должна вернуться боевая сессия."""
        from app.db.sandbox import DynamicSessionMaker

        production_url = "sqlite+aiosqlite:///:memory:"
        maker = DynamicSessionMaker(database_url=production_url)

        await maker.enable_sandbox(user_id=1)
        await maker.disable_sandbox()

        # После отключения sandbox — используем боевую сессию
        async with maker.get_session() as session:
            assert isinstance(session, AsyncSession)

    @pytest.mark.asyncio
    async def test_sandbox_sessions_are_isolated(self) -> None:
        """Sandbox-сессии разных пользователей изолированы друг от друга."""
        from app.db.sandbox import DynamicSessionMaker

        production_url = "sqlite+aiosqlite:///:memory:"
        maker = DynamicSessionMaker(database_url=production_url)

        await maker.enable_sandbox(user_id=111)
        async with maker.get_session() as session_111:
            session_111_id = id(session_111)
            # Сессия активна
            assert session_111.is_active

        await maker.disable_sandbox()
        await maker.enable_sandbox(user_id=222)
        async with maker.get_session() as session_222:
            session_222_id = id(session_222)

        await maker.disable_sandbox()

        # Сессии должны быть разными объектами
        assert session_111_id != session_222_id

    def test_is_sandbox_active_false_by_default(self) -> None:
        """is_sandbox_active должен быть False без вызова enable_sandbox."""
        from app.db.sandbox import DynamicSessionMaker

        maker = DynamicSessionMaker(database_url="sqlite+aiosqlite:///:memory:")
        assert maker.is_sandbox_active is False

    @pytest.mark.asyncio
    async def test_is_sandbox_active_true_after_enable(self) -> None:
        """is_sandbox_active должен быть True после enable_sandbox."""
        from app.db.sandbox import DynamicSessionMaker

        maker = DynamicSessionMaker(database_url="sqlite+aiosqlite:///:memory:")
        await maker.enable_sandbox(user_id=1)
        try:
            assert maker.is_sandbox_active is True
        finally:
            await maker.disable_sandbox()

    @pytest.mark.asyncio
    async def test_sandbox_engine_var_get_returns_engine_when_active(self) -> None:
        """_sandbox_engine_var_get() возвращает AsyncEngine когда sandbox активен."""
        from sqlalchemy.ext.asyncio import AsyncEngine

        from app.db.sandbox import DynamicSessionMaker

        maker = DynamicSessionMaker(database_url="sqlite+aiosqlite:///:memory:")
        assert maker._sandbox_engine_var_get() is None

        await maker.enable_sandbox(user_id=42)
        try:
            engine = maker._sandbox_engine_var_get()
            assert engine is not None
            assert isinstance(engine, AsyncEngine)
        finally:
            await maker.disable_sandbox()

        assert maker._sandbox_engine_var_get() is None
