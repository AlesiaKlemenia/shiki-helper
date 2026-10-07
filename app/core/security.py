"""
Шифрование и расшифровка OAuth-токенов через Fernet (симметричное шифрование).

Используется для безопасного хранения refresh_token Google OAuth в базе данных.
Ключ шифрования задаётся через переменную окружения ENCRYPTION_KEY.

Использование:
    from app.core.security import TokenEncryptor
    from app.config import settings

    encryptor = TokenEncryptor(key=settings.encryption_key)
    encrypted = encryptor.encrypt(refresh_token)
    token = encryptor.decrypt(encrypted_from_db)
"""
from __future__ import annotations

import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


logger = logging.getLogger(__name__)


class TokenEncryptor:
    """Шифрует и расшифровывает строковые токены с помощью Fernet.

    Fernet гарантирует симметричное шифрование (AES-128-CBC) с HMAC-подписью,
    что обеспечивает как конфиденциальность, так и целостность данных.

    Args:
        key: Fernet-ключ в виде строки (base64url, 32 байта).
             Генерация: Fernet.generate_key().decode()

    Raises:
        ValueError: Если переданный ключ имеет некорректный формат.
    """

    def __init__(self, key: str) -> None:
        """Инициализирует шифратор с заданным ключом.

        Args:
            key: Fernet-ключ в виде строки.

        Raises:
            ValueError: При некорректном формате ключа.
        """
        try:
            self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        except Exception as exc:
            raise ValueError(
                f"Некорректный Fernet-ключ. "
                f"Используйте: Fernet.generate_key().decode(). "
                f"Ошибка: {exc}"
            ) from exc

    def encrypt(self, token: str) -> str:
        """Шифрует строковый токен.

        Каждый вызов производит уникальный шифротекст (благодаря случайному IV).

        Args:
            token: Открытый текст для шифрования (например, refresh_token).

        Returns:
            Зашифрованный токен в виде строки (base64url).
        """
        encrypted_bytes = self._fernet.encrypt(token.encode("utf-8"))
        return encrypted_bytes.decode("utf-8")

    def decrypt(self, encrypted_token: str) -> Optional[str]:
        """Расшифровывает токен.

        При любой ошибке (неверный ключ, испорченные данные, пустая строка)
        возвращает None и логирует ошибку — не бросает исключение в caller.

        Args:
            encrypted_token: Зашифрованный токен (результат encrypt()).

        Returns:
            Расшифрованный токен или None при ошибке.
        """
        if not encrypted_token:
            logger.warning("decrypt(): получена пустая строка, возвращаем None")
            return None

        try:
            decrypted_bytes = self._fernet.decrypt(
                encrypted_token.encode("utf-8")
            )
            return decrypted_bytes.decode("utf-8")
        except InvalidToken:
            logger.error(
                "decrypt(): не удалось расшифровать токен — "
                "возможно, неверный ключ или испорченные данные"
            )
            return None
        except Exception as exc:
            logger.error(
                "decrypt(): непредвиденная ошибка при расшифровке: %s", exc
            )
            return None
