"""
R4.3 FIX — Encryption-at-rest integration layer.

Provides encrypt/decrypt helpers that use the existing Vault/Fernet
infrastructure. Used by persist_result and read paths to ensure
sensitive data is never stored as plaintext.
"""
import json
import os
from cryptography.fernet import Fernet, InvalidToken


def _get_fernet_key() -> str:
    """Resolve Fernet key from environment or settings."""
    # Check env first (works in tests and production)
    key = os.environ.get("VAULT_FERNET_KEY", "")
    if key:
        return key
    # Fallback to settings
    try:
        from ..config import get_settings
        s = get_settings()
        key = getattr(s, "privacy_vault_key", "") or getattr(s, "vault_fernet_key", "")
        if key:
            return key
    except Exception:
        pass
    return ""


def _get_hmac_secret() -> str:
    """Resolve HMAC secret from environment or settings."""
    secret = os.environ.get("PRIVACY_HMAC_SECRET", "")
    if secret:
        return secret
    try:
        from ..config import get_settings
        s = get_settings()
        key = getattr(s, "privacy_hmac_secret", "")
        if key:
            return key
    except Exception:
        pass
    return ""


def get_encryption_service():
    """Get a PrivacyEncryptionService instance with resolved keys."""
    from .privacy import PrivacyEncryptionService
    fernet_key = _get_fernet_key()
    hmac_secret = _get_hmac_secret()
    if not fernet_key:
        # Generate a development key if none configured
        fernet_key = Fernet.generate_key().decode()
    if not hmac_secret:
        hmac_secret = "dev-hmac-secret"
    return PrivacyEncryptionService(fernet_key=fernet_key, hmac_secret=hmac_secret)


def encrypt_json(data: dict) -> str:
    """Encrypt a dict to Fernet ciphertext string."""
    svc = get_encryption_service()
    plaintext = json.dumps(data, ensure_ascii=False)
    return svc.encrypt(plaintext)


def decrypt_json(ciphertext: str) -> dict:
    """Decrypt a Fernet ciphertext string back to dict."""
    if not ciphertext:
        return {}
    svc = get_encryption_service()
    plaintext = svc.decrypt(ciphertext)
    if not plaintext:
        return {}
    return json.loads(plaintext)


def encrypt_text(text: str) -> str:
    """Encrypt a plain text string."""
    if not text:
        return ""
    svc = get_encryption_service()
    return svc.encrypt(text)


def decrypt_text(ciphertext: str) -> str:
    """Decrypt a ciphertext string back to plain text."""
    if not ciphertext:
        return ""
    svc = get_encryption_service()
    return svc.decrypt(ciphertext)


def blind_index(value: str) -> str:
    """Create HMAC blind index for searchable encryption."""
    if not value:
        return ""
    svc = get_encryption_service()
    return svc.blind_index(value)
