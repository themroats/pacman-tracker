"""
Token encryption/decryption utility for Strava OAuth tokens.

Uses Fernet symmetric encryption from the `cryptography` library.
"""

from cryptography.fernet import Fernet

from app.config import get_settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Return a cached Fernet instance derived from SECRET_KEY."""
    global _fernet
    if _fernet is None:
        settings = get_settings()
        # Derive a Fernet key from the secret_key
        # Fernet requires a 32-byte URL-safe base64-encoded key.
        # We derive one by padding/hashing the secret.
        import base64
        import hashlib

        key_bytes = hashlib.sha256(settings.secret_key.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        _fernet = Fernet(fernet_key)
    return _fernet


def encrypt_token(plain_text: str) -> str:
    """Encrypt a plaintext token string and return the ciphertext as a UTF-8 string."""
    f = _get_fernet()
    return f.encrypt(plain_text.encode()).decode()


def decrypt_token(cipher_text: str) -> str:
    """Decrypt a ciphertext string and return the original plaintext."""
    f = _get_fernet()
    return f.decrypt(cipher_text.encode()).decode()


def compute_token_hash(plain_text: str) -> str:
    """Return a SHA-256 hex digest of *plain_text* for O(1) indexed lookup."""
    import hashlib

    return hashlib.sha256(plain_text.encode()).hexdigest()


def reset_fernet() -> None:
    """Reset the cached Fernet instance (for testing)."""
    global _fernet
    _fernet = None
