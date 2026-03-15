"""
Unit tests for token encryption/decryption service.

Tests:
- Round-trip encrypt → decrypt
- Different inputs produce different ciphertexts
- Tampered ciphertext fails to decrypt
- Empty string round-trip
"""

from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _mock_settings():
    """Patch get_settings so crypto doesn't need a real .env."""
    mock_settings = MagicMock()
    mock_settings.secret_key = "test-secret-key-for-unit-tests"
    with patch("app.services.crypto.get_settings", return_value=mock_settings):
        from app.services.crypto import reset_fernet
        reset_fernet()
        yield
        reset_fernet()


class TestEncryptDecryptRoundTrip:
    """Encrypt then decrypt should return the original value."""

    def test_basic_round_trip(self):
        from app.services.crypto import encrypt_token, decrypt_token

        original = "fake_access_token_abc123"
        encrypted = encrypt_token(original)
        assert encrypted != original
        assert decrypt_token(encrypted) == original

    def test_empty_string(self):
        from app.services.crypto import encrypt_token, decrypt_token

        encrypted = encrypt_token("")
        assert decrypt_token(encrypted) == ""

    def test_unicode_round_trip(self):
        from app.services.crypto import encrypt_token, decrypt_token

        original = "tökën_wïth_ünïcödé_🔑"
        assert decrypt_token(encrypt_token(original)) == original

    def test_long_token(self):
        from app.services.crypto import encrypt_token, decrypt_token

        original = "x" * 10_000
        assert decrypt_token(encrypt_token(original)) == original


class TestEncryptionProperties:
    """Verify encryption behaves correctly."""

    def test_different_inputs_different_ciphertexts(self):
        from app.services.crypto import encrypt_token

        a = encrypt_token("token_a")
        b = encrypt_token("token_b")
        assert a != b

    def test_same_input_different_ciphertexts(self):
        """Fernet uses a random IV, so encrypting the same value twice should differ."""
        from app.services.crypto import encrypt_token

        a = encrypt_token("same_token")
        b = encrypt_token("same_token")
        assert a != b

    def test_tampered_ciphertext_raises(self):
        from cryptography.fernet import InvalidToken
        from app.services.crypto import encrypt_token, decrypt_token

        encrypted = encrypt_token("real_token")
        tampered = encrypted[:-4] + "XXXX"
        with pytest.raises(Exception):
            decrypt_token(tampered)
