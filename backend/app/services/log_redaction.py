"""
R4.3-8: Log Redaction Utility

Provides a logging filter that automatically redacts sensitive data
from log messages before they are written to log files.
"""
import logging
import re
from typing import Set


# Patterns that indicate sensitive data
SENSITIVE_PATTERNS = [
    # Passwords
    (re.compile(r'(password["\s:=]+)["\']?[^"\',\s}]+["\']?', re.IGNORECASE), r'\1***REDACTED***'),
    # Tokens (JWT, Bearer, etc.)
    (re.compile(r'(Bearer\s+)[A-Za-z0-9\-._~+/]+=*', re.IGNORECASE), r'\1***REDACTED***'),
    (re.compile(r'(token["\s:=]+)["\']?[^"\',\s}]+["\']?', re.IGNORECASE), r'\1***REDACTED***'),
    (re.compile(r'(authorization["\s:=]+)["\']?[^"\',\s}]+["\']?', re.IGNORECASE), r'\1***REDACTED***'),
    # Passport numbers
    (re.compile(r'(passport_number["\s:=]+)["\']?[^"\',\s}]+["\']?', re.IGNORECASE), r'\1***REDACTED***'),
    # ID card numbers (Chinese ID: 18 digits)
    (re.compile(r'(id_card_number["\s:=]+)["\']?\d{17}[\dXx]["\']?', re.IGNORECASE), r'\1***REDACTED***'),
    # Fernet keys / encryption keys
    (re.compile(r'(fernet_key["\s:=]+)["\']?[^"\',\s}]+["\']?', re.IGNORECASE), r'\1***REDACTED***'),
    (re.compile(r'(secret_key["\s:=]+)["\']?[^"\',\s}]+["\']?', re.IGNORECASE), r'\1***REDACTED***'),
    # API keys
    (re.compile(r'(api_key["\s:=]+)["\']?[^"\',\s}]+["\']?', re.IGNORECASE), r'\1***REDACTED***'),
    # Admin token
    (re.compile(r'(admin_token["\s:=]+)["\']?[^"\',\s}]+["\']?', re.IGNORECASE), r'\1***REDACTED***'),
]

# Keys that should always be redacted in JSON-like structures
SENSITIVE_KEYS: Set[str] = {
    "password", "token", "authorization", "secret",
    "passport_number", "id_card_number", "passport",
    "fernet_key", "api_key", "payment_key", "admin_token",
    "jwt_secret", "vault_key", "credit_card", "ssn",
}


class SensitiveDataFilter(logging.Filter):
    """
    Logging filter that redacts sensitive data from log messages.

    Usage:
        handler.addFilter(SensitiveDataFilter())
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive data from the log message."""
        if isinstance(record.msg, str):
            record.msg = self._redact(record.msg)
        return True

    def _redact(self, message: str) -> str:
        """Apply all redaction patterns to the message."""
        for pattern, replacement in SENSITIVE_PATTERNS:
            message = pattern.sub(replacement, message)
        return message


def redact_sensitive_data(data: dict) -> dict:
    """
    Redact sensitive fields from a dictionary.

    This is useful for logging request/response bodies
    without exposing sensitive information.
    """
    if not isinstance(data, dict):
        return data

    redacted = {}
    for key, value in data.items():
        if key.lower() in SENSITIVE_KEYS:
            redacted[key] = "***REDACTED***"
        elif isinstance(value, dict):
            redacted[key] = redact_sensitive_data(value)
        elif isinstance(value, list):
            redacted[key] = [
                redact_sensitive_data(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            redacted[key] = value

    return redacted


def mask_string(value: str, visible_chars: int = 4) -> str:
    """
    Mask a string, showing only the last N characters.

    Example: mask_string("E12345678", 4) -> "****5678"
    """
    if not value or len(value) <= visible_chars:
        return "***"
    return "*" * (len(value) - visible_chars) + value[-visible_chars:]


def setup_log_redaction():
    """
    Install the sensitive data filter on all root logger handlers.

    Call this during application startup.
    """
    root_logger = logging.getLogger()
    sensitive_filter = SensitiveDataFilter()

    for handler in root_logger.handlers:
        handler.addFilter(sensitive_filter)

    # Also add to uvicorn loggers
    for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
        uv_logger = logging.getLogger(logger_name)
        uv_logger.addFilter(sensitive_filter)
