"""
Тесты для app/core/logger.py — настройка структурированного логирования.

Стратегия: TDD Red Phase — тесты написаны ДО реализации.
"""
from __future__ import annotations

import logging


class TestSetupLogging:
    """Тесты функции setup_logging()."""

    def test_setup_logging_sets_root_level_info(self) -> None:
        """По умолчанию уровень логирования должен быть INFO."""
        from app.core.logger import setup_logging

        setup_logging("INFO")
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

    def test_setup_logging_sets_root_level_debug(self) -> None:
        """При level='DEBUG' корневой логгер должен принять уровень DEBUG."""
        from app.core.logger import setup_logging

        setup_logging("DEBUG")
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_setup_logging_sets_root_level_warning(self) -> None:
        """При level='WARNING' корневой логгер должен принять уровень WARNING."""
        from app.core.logger import setup_logging

        setup_logging("WARNING")
        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING

    def test_setup_logging_adds_handler(self) -> None:
        """После вызова setup_logging корневой логгер должен иметь хотя бы один хэндлер."""
        from app.core.logger import setup_logging

        # Сбрасываем хэндлеры перед тестом
        logging.getLogger().handlers.clear()
        setup_logging("INFO")
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) >= 1

    def test_setup_logging_handler_is_stream_handler(self) -> None:
        """Хэндлер должен быть StreamHandler (вывод в stdout/stderr)."""
        from app.core.logger import setup_logging

        logging.getLogger().handlers.clear()
        setup_logging("INFO")
        root_logger = logging.getLogger()
        has_stream = any(
            isinstance(h, logging.StreamHandler)
            for h in root_logger.handlers
        )
        assert has_stream, "Должен быть хотя бы один StreamHandler"

    def test_setup_logging_no_duplicate_handlers(self) -> None:
        """Повторный вызов setup_logging не должен добавлять дублирующие хэндлеры."""
        from app.core.logger import setup_logging

        logging.getLogger().handlers.clear()
        setup_logging("INFO")
        setup_logging("INFO")
        root_logger = logging.getLogger()
        stream_handlers = [
            h for h in root_logger.handlers
            if isinstance(h, logging.StreamHandler)
        ]
        assert len(stream_handlers) == 1, (
            "Повторный вызов setup_logging не должен дублировать хэндлеры"
        )

    def test_get_logger_returns_named_logger(self) -> None:
        """get_logger('mymodule') должен возвращать логгер с именем 'mymodule'."""
        from app.core.logger import get_logger

        logger = get_logger("mymodule")
        assert logger.name == "mymodule"

    def test_get_logger_returns_logger_instance(self) -> None:
        """get_logger должен возвращать экземпляр logging.Logger."""
        from app.core.logger import get_logger

        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)
