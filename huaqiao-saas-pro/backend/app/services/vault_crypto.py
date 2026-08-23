import json

from cryptography.fernet import Fernet, InvalidToken

from ..config import get_settings


class VaultConfigError(RuntimeError):
    """Raised when vault encryption is not properly configured."""
    pass


def _fernet() -> Fernet:
    """Get Fernet instance. Raises VaultConfigError if not configured."""
    key = (get_settings().vault_fernet_key or "").strip()
    if not key:
        raise VaultConfigError(
            "VAULT_FERNET_KEY is not configured. "
            "Customer vault encryption is required for production use. "
            "Generate a key with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )
    try:
        return Fernet(key.encode("utf-8") if isinstance(key, str) else key)
    except Exception as e:
        raise VaultConfigError(f"Invalid VAULT_FERNET_KEY: {e}")


def validate_vault_config():
    """Validate vault configuration at startup. Call during app initialization."""
    _fernet()  # Will raise VaultConfigError if not configured


def encrypt_profile_json(data: dict) -> str:
    f = _fernet()
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return f.encrypt(raw).decode("utf-8")


def decrypt_profile_json(cipher_text: str) -> dict:
    if not cipher_text:
        return {}
    f = _fernet()
    try:
        raw = f.decrypt(cipher_text.encode("utf-8"))
    except InvalidToken:
        raise ValueError("Failed to decrypt vault data: invalid token")
    return json.loads(raw.decode("utf-8"))
