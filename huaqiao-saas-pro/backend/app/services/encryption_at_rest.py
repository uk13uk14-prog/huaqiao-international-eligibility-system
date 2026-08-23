"""
R4.3 FIX — Encryption-at-rest integration layer (SaaS Pro).

Uses the existing vault_crypto Fernet infrastructure.
"""
import json
import os
from cryptography.fernet import Fernet, InvalidToken


def _get_fernet() -> Fernet:
    """Get Fernet instance from vault_crypto."""
    from .vault_crypto import _fernet
    return _fernet()


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
    return "saas-hmac-default"


def encrypt_json(data: dict) -> str:
    """Encrypt a dict to Fernet ciphertext string."""
    f = _get_fernet()
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return f.encrypt(raw).decode("utf-8")


def decrypt_json(ciphertext: str) -> dict:
    """Decrypt a Fernet ciphertext string back to dict."""
    if not ciphertext or ciphertext == "[ENCRYPTED]":
        return {}
    f = _get_fernet()
    try:
        raw = f.decrypt(ciphertext.encode("utf-8"))
    except InvalidToken:
        return {}
    return json.loads(raw.decode("utf-8"))


def encrypt_text(text: str) -> str:
    """Encrypt a plain text string."""
    if not text:
        return ""
    f = _get_fernet()
    return f.encrypt(text.encode("utf-8")).decode("utf-8")


def decrypt_text(ciphertext: str) -> str:
    """Decrypt a ciphertext string back to plain text."""
    if not ciphertext or ciphertext == "[ENCRYPTED]":
        return ""
    f = _get_fernet()
    try:
        return f.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ""


def blind_index(value: str) -> str:
    """Create HMAC blind index for searchable encryption."""
    import hashlib
    import hmac as hmac_mod
    if not value:
        return ""
    secret = _get_hmac_secret()
    return hmac_mod.new(
        secret.encode(),
        value.encode(),
        hashlib.sha256
    ).hexdigest()
