"""
Выбор FSM Storage для aiogram: Redis с graceful degradation на MemoryStorage.

При каждом старте бота:
1. Если REDIS_URL не задан — используется MemoryStorage.
2. Если REDIS_URL задан — проверяется доступность через PING.
3. Если PING успешен — используется RedisStorage (персистентные состояния).
4. Если PING упал — логируется предупреждение, используется MemoryStorage.

Использование:
    from app.bot.storage import create_storage
    from app.config import settings

    storage = await create_storage(settings.redis_url)
    dp = Dispatcher(storage=storage)
"""
from __future__ import annotations

import logging
from typing import Optional, Union

import redis.asyncio as redis
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import DefaultKeyBuilder, RedisStorage


logger = logging.getLogger(__name__)


async def create_storage(
    redis_url: Optional[str],
) -> Union[RedisStorage, MemoryStorage]:
    """Создаёт FSM Storage с автоматическим fallback на MemoryStorage.

    Проверяет доступность Redis через PING перед подключением.
    При любой ошибке подключения безопасно возвращает MemoryStorage.

    Args:
        redis_url: URL подключения к Redis или None.
            None → немедленный fallback на MemoryStorage.
            Пример: 'redis://localhost:6379/0'

    Returns:
        RedisStorage если Redis доступен, иначе MemoryStorage.
    """
    if redis_url is None:
        logger.info(
            "REDIS_URL не задан — используется MemoryStorage. "
            "FSM-состояния не будут сохранены между перезапусками."
        )
        return MemoryStorage()

    try:
        client = redis.from_url(redis_url, decode_responses=False)
        await client.ping()
        logger.info("Redis доступен (%s) — используется RedisStorage.", redis_url)
        # aiogram-dialog хранит контексты/стеки/данные под ключами с destiny.
        # DefaultKeyBuilder по умолчанию destiny не поддерживает (=False), из-за чего
        # на каждом апдейте падает ValueError и команды не отвечают.
        return RedisStorage(
            redis=client,
            key_builder=DefaultKeyBuilder(with_destiny=True),
        )

    except Exception as exc:
        logger.warning(
            "Redis недоступен (%s): %s. "
            "Переключаемся на MemoryStorage — состояния не будут персистентны.",
            redis_url,
            exc,
        )
        return MemoryStorage()
