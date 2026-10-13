"""
Настройка структурированного логирования для Shiki-Helper.

Использование:
    from app.core.logger import setup_logging, get_logger

    setup_logging("INFO")
    logger = get_logger(__name__)
    logger.info("Бот запущен", extra={"user_id": 12345})
"""
from __future__ import annotations

import logging
import sys


_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str = "INFO") -> None:
    """Настраивает корневой логгер с форматированным StreamHandler.

    Функция идемпотентна: повторный вызов не добавляет дублирующих хэндлеров.

    Args:
        level: Уровень логирования в виде строки (DEBUG/INFO/WARNING/ERROR).
               Нечувствителен к регистру.

    Raises:
        ValueError: Если передан неизвестный уровень логирования.
    """
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Неизвестный уровень логирования: {level!r}")

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Проверяем, не добавлен ли уже StreamHandler (идемпотентность)
    has_stream_handler = any(
        isinstance(handler, logging.StreamHandler)
        and not isinstance(handler, logging.FileHandler)
        for handler in root_logger.handlers
    )

    if not has_stream_handler:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(numeric_level)
        formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    # Снижаем шумность сторонних библиотек, но оставляем логирование апдейтов aiogram
    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Возвращает именованный логгер для модуля.

    Args:
        name: Имя логгера, обычно передаётся `__name__`.

    Returns:
        Настроенный экземпляр logging.Logger.
    """
    return logging.getLogger(name)
