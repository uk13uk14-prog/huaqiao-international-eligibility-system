import base64
import json

from cryptography.fernet import Fernet, InvalidToken

from ..config import get_settings


def _fernet() -> Fernet | None:
    key = (get_settings().vault_fernet_key or "").strip()
    if not key:
        return None
    try:
        return Fernet(key.encode("utf-8") if isinstance(key, str) else key)
    except Exception:
        return None


def encrypt_profile_json(data: dict) -> str:
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    f = _fernet()
    if f:
        return f.encrypt(raw).decode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def decrypt_profile_json(cipher_text: str) -> dict:
    if not cipher_text:
        return {}
    f = _fernet()
    if f:
        try:
            raw = f.decrypt(cipher_text.encode("utf-8"))
        except InvalidToken:
            raw = base64.urlsafe_b64decode(cipher_text.encode("utf-8"))
    else:
        raw = base64.urlsafe_b64decode(cipher_text.encode("utf-8"))
    return json.loads(raw.decode("utf-8"))
