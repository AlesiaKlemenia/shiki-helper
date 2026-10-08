"""
Тесты для app/core/security.py — шифрование/расшифровка OAuth-токенов.

Стратегия: TDD Red Phase — тесты написаны ДО реализации.
"""
from __future__ import annotations


import pytest


def make_valid_key() -> str:
    """Генерирует корректный Fernet-ключ (base64url, 32 байта) для тестов."""
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode()


class TestTokenEncryptor:
    """Тесты класса TokenEncryptor."""

    def test_encrypt_returns_string(self) -> None:
        """encrypt() должен возвращать строку (зашифрованный токен)."""
        from app.core.security import TokenEncryptor

        encryptor = TokenEncryptor(key=make_valid_key())
        result = encryptor.encrypt("my_oauth_token")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_encrypt_decrypt_roundtrip(self) -> None:
        """Зашифрованный токен должен корректно расшифровываться."""
        from app.core.security import TokenEncryptor

        key = make_valid_key()
        encryptor = TokenEncryptor(key=key)
        original = "ya29.some_google_refresh_token_value"

        encrypted = encryptor.encrypt(original)
        decrypted = encryptor.decrypt(encrypted)

        assert decrypted == original

    def test_encrypt_produces_different_ciphertext(self) -> None:
        """Каждое шифрование одного и того же токена даёт разный шифротекст (Fernet использует IV)."""
        from app.core.security import TokenEncryptor

        key = make_valid_key()
        encryptor = TokenEncryptor(key=key)
        token = "my_secret_token"

        encrypted1 = encryptor.encrypt(token)
        encrypted2 = encryptor.encrypt(token)

        # Шифротексты должны отличаться (разные nonce/IV)
        assert encrypted1 != encrypted2

    def test_decrypt_with_wrong_key_returns_none(self) -> None:
        """Расшифровка чужим ключом должна возвращать None (не бросать исключение)."""
        from app.core.security import TokenEncryptor

        key1 = make_valid_key()
        key2 = make_valid_key()

        encryptor1 = TokenEncryptor(key=key1)
        encryptor2 = TokenEncryptor(key=key2)

        encrypted = encryptor1.encrypt("secret_token")
        result = encryptor2.decrypt(encrypted)

        assert result is None

    def test_decrypt_with_corrupted_data_returns_none(self) -> None:
        """Расшифровка испорченных данных должна возвращать None."""
        from app.core.security import TokenEncryptor

        encryptor = TokenEncryptor(key=make_valid_key())
        result = encryptor.decrypt("this_is_not_valid_fernet_token!!!!")

        assert result is None

    def test_decrypt_with_empty_string_returns_none(self) -> None:
        """Расшифровка пустой строки должна возвращать None."""
        from app.core.security import TokenEncryptor

        encryptor = TokenEncryptor(key=make_valid_key())
        result = encryptor.decrypt("")

        assert result is None

    def test_encrypt_empty_string(self) -> None:
        """Шифрование пустой строки должно работать и быть обратимым."""
        from app.core.security import TokenEncryptor

        encryptor = TokenEncryptor(key=make_valid_key())
        encrypted = encryptor.encrypt("")
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == ""

    def test_constructor_raises_on_invalid_key(self) -> None:
        """Конструктор должен выбросить ValueError при некорректном ключе."""
        from app.core.security import TokenEncryptor

        with pytest.raises((ValueError, Exception)):
            TokenEncryptor(key="not_a_valid_fernet_key")
