"""
R4.3 Privacy & Data Protection Module

This module provides:
1. Field-level encryption for sensitive data using Fernet (existing Vault infrastructure)
2. Blind index for searchable encrypted fields (HMAC-based)
3. API response masking for sensitive fields
4. Log redaction for sensitive data
5. Data retention policy configuration
6. Audit logging for sensitive data access
"""

import hashlib
import hmac
import json
import logging
import re
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classification
# =============================================================================

class DataClassification(str, Enum):
    PUBLIC = "public"
    PERSONAL = "personal"
    SENSITIVE = "sensitive"
    HIGHLY_SENSITIVE = "highly_sensitive"


# Fields that require encryption at rest
SENSITIVE_FIELDS: Dict[str, DataClassification] = {
    # Free backend UserInfo
    "birth_date": DataClassification.SENSITIVE,
    "passport_info": DataClassification.HIGHLY_SENSITIVE,
    "household_info": DataClassification.HIGHLY_SENSITIVE,
    "residence_records": DataClassification.HIGHLY_SENSITIVE,
    # EligibilityRecord (both backends)
    "raw_input": DataClassification.HIGHLY_SENSITIVE,
    # SaaS User
    "email": DataClassification.PERSONAL,
    # Consultation
    "phone": DataClassification.PERSONAL,
    "contact_phone": DataClassification.PERSONAL,
    "contact_email": DataClassification.PERSONAL,
}

# Fields that need blind index for searchable encryption
INDEXED_SENSITIVE_FIELDS: Set[str] = {
    "passport_info",
    "household_info",
}


# =============================================================================
# Encryption Service
# =============================================================================

class PrivacyEncryptionError(Exception):
    """Raised when encryption/decryption fails."""
    pass


class PrivacyEncryptionService:
    """
    Field-level encryption using Fernet (reuses existing Vault infrastructure).
    
    - Encrypt: plaintext → ciphertext (stored in DB)
    - Decrypt: ciphertext → plaintext (only for authorized business flows)
    - Blind Index: HMAC for searchable encryption (equality queries only)
    """

    def __init__(self, fernet_key: str, hmac_secret: str):
        """
        Args:
            fernet_key: Fernet key for encryption (same as VAULT_FERNET_KEY)
            hmac_secret: Secret for blind index HMAC (separate from encryption key)
        """
        if not fernet_key:
            raise PrivacyEncryptionError("Fernet key is required for encryption")
        if not hmac_secret:
            raise PrivacyEncryptionError("HMAC secret is required for blind index")
        
        self._fernet = Fernet(fernet_key.encode() if isinstance(fernet_key, str) else fernet_key)
        self._hmac_secret = hmac_secret.encode() if isinstance(hmac_secret, str) else hmac_secret

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext to ciphertext."""
        if not plaintext:
            return ""
        try:
            return self._fernet.encrypt(plaintext.encode()).decode()
        except Exception as e:
            raise PrivacyEncryptionError(f"Encryption failed: {e}")

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext to plaintext."""
        if not ciphertext:
            return ""
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken:
            raise PrivacyEncryptionError("Decryption failed: invalid token or wrong key")
        except Exception as e:
            raise PrivacyEncryptionError(f"Decryption failed: {e}")

    def blind_index(self, value: str) -> str:
        """
        Create a keyed hash for searchable encryption.
        Uses HMAC-SHA256 with a secret key (not plain SHA256).
        """
        if not value:
            return ""
        return hmac.new(
            self._hmac_secret,
            value.encode(),
            hashlib.sha256
        ).hexdigest()

    def encrypt_json(self, data: dict) -> str:
        """Encrypt a JSON-serializable dict."""
        return self.encrypt(json.dumps(data, ensure_ascii=False))

    def decrypt_json(self, ciphertext: str) -> dict:
        """Decrypt to a dict."""
        plaintext = self.decrypt(ciphertext)
        if not plaintext:
            return {}
        return json.loads(plaintext)


# =============================================================================
# API Response Masking
# =============================================================================

def mask_passport(value: str) -> str:
    """Mask passport number: show last 4 chars."""
    if not value or len(value) < 4:
        return "****"
    return "****" + value[-4:]


def mask_id_card(value: str) -> str:
    """Mask ID card number: show last 4 chars."""
    if not value or len(value) < 4:
        return "****"
    return "****" + value[-4:]


def mask_email(value: str) -> str:
    """Mask email: show first char and domain."""
    if not value or "@" not in value:
        return "***"
    local, domain = value.split("@", 1)
    if len(local) <= 1:
        return f"*@{domain}"
    return f"{local[0]}***@{domain}"


def mask_phone(value: str) -> str:
    """Mask phone: show last 4 chars."""
    if not value or len(value) < 4:
        return "****"
    return "****" + value[-4:]


# Fields that should be masked in API responses
MASK_FUNCTIONS = {
    "passport_info": mask_passport,
    "passport_number": mask_passport,
    "id_card_number": mask_id_card,
    "id_card": mask_id_card,
    "email": mask_email,
    "contact_email": mask_email,
    "phone": mask_phone,
    "contact_phone": mask_phone,
}


def mask_sensitive_fields(data: dict, fields_to_mask: Optional[Set[str]] = None) -> dict:
    """
    Mask sensitive fields in a dict for API response.
    
    Args:
        data: The dict to mask
        fields_to_mask: Specific fields to mask. If None, uses MASK_FUNCTIONS keys.
    
    Returns:
        A new dict with sensitive fields masked.
    """
    if fields_to_mask is None:
        fields_to_mask = set(MASK_FUNCTIONS.keys())
    
    result = {}
    for key, value in data.items():
        if key in fields_to_mask and key in MASK_FUNCTIONS and isinstance(value, str):
            result[key] = MASK_FUNCTIONS[key](value)
        elif isinstance(value, dict):
            result[key] = mask_sensitive_fields(value, fields_to_mask)
        elif isinstance(value, list):
            result[key] = [
                mask_sensitive_fields(item, fields_to_mask) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def mask_raw_input(raw_input_json: str) -> str:
    """
    Mask sensitive fields in the raw_input JSON string.
    This is used when returning eligibility records via API.
    """
    if not raw_input_json or raw_input_json == "{}":
        return raw_input_json
    
    try:
        data = json.loads(raw_input_json)
        masked = mask_sensitive_fields(data)
        return json.dumps(masked, ensure_ascii=False)
    except (json.JSONDecodeError, TypeError):
        return raw_input_json


# =============================================================================
# Log Redaction
# =============================================================================

# Patterns to redact in logs
REDACTION_PATTERNS = [
    (re.compile(r'(password["\s:=]+)[^\s,}"\']+', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'(token["\s:=]+)[^\s,}"\']+', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'(authorization["\s:=]+)[^\s,}"\']+', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'(passport_number["\s:=]+)[^\s,}"\']+', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'(passport_info["\s:=]+)[^\s,}"\']+', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'(id_card_number["\s:=]+)[^\s,}"\']+', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'(fernet_key["\s:=]+)[^\s,}"\']+', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'(api_key["\s:=]+)[^\s,}"\']+', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'(secret["\s:=]+)[^\s,}"\']+', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'(hmac_secret["\s:=]+)[^\s,}"\']+', re.IGNORECASE), r'\1[REDACTED]'),
]


def redact_log_message(message: str) -> str:
    """Redact sensitive data from log messages."""
    result = message
    for pattern, replacement in REDACTION_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


class RedactingFormatter(logging.Formatter):
    """Logging formatter that redacts sensitive data."""
    
    def format(self, record: logging.LogRecord) -> str:
        record.msg = redact_log_message(str(record.msg))
        if record.args:
            # Redact args if they contain sensitive data
            try:
                record.args = tuple(
                    redact_log_message(str(arg)) if isinstance(arg, str) else arg
                    for arg in record.args
                )
            except (TypeError, AttributeError):
                pass
        return super().format(record)


# =============================================================================
# Data Retention Policy
# =============================================================================

class RetentionPeriod:
    """Business retention policy (NOT legal requirement)."""
    
    # Active case: retain during service period
    ACTIVE_CASE = None  # No expiry
    
    # Closed case: default 12 months
    CLOSED_CASE_MONTHS = 12
    
    # Uploaded sensitive documents: 6 months after case closed
    SENSITIVE_DOCUMENTS_MONTHS = 6
    
    # Security/audit logs: 24 months
    SECURITY_LOGS_MONTHS = 24
    
    # Eligibility records: 12 months after creation
    ELIGIBILITY_RECORDS_MONTHS = 12

    @classmethod
    def get_retention_date(cls, record_type: str, created_at: datetime) -> Optional[datetime]:
        """
        Get the date after which a record should be deleted/anonymized.
        
        Args:
            record_type: Type of record (e.g., 'eligibility_record', 'uploaded_document')
            created_at: When the record was created
        
        Returns:
            Date after which the record should be deleted, or None for active cases.
        """
        if record_type == "active_case":
            return None
        elif record_type == "eligibility_record":
            return created_at + timedelta(days=cls.ELIGIBILITY_RECORDS_MONTHS * 30)
        elif record_type == "sensitive_document":
            return created_at + timedelta(days=cls.SENSITIVE_DOCUMENTS_MONTHS * 30)
        elif record_type == "security_log":
            return created_at + timedelta(days=cls.SECURITY_LOGS_MONTHS * 30)
        elif record_type == "closed_case":
            return created_at + timedelta(days=cls.CLOSED_CASE_MONTHS * 30)
        return None


# =============================================================================
# Audit Log
# =============================================================================

class AuditAction(str, Enum):
    VIEW_SENSITIVE_DATA = "view_sensitive_data"
    DOWNLOAD_DOCUMENT = "download_document"
    MODIFY_ELIGIBILITY = "modify_eligibility"
    DELETE_USER_DATA = "delete_user_data"
    ADMIN_ACCESS_PROFILE = "admin_access_profile"
    EXPORT_DATA = "export_data"
    DECRYPT_FIELD = "decrypt_field"


class AuditLogger:
    """
    Audit logger for sensitive data access.
    
    Records: actor, action, resource_type, resource_id, timestamp
    Does NOT record sensitive payload.
    """

    def __init__(self, logger_name: str = "privacy_audit"):
        self._logger = logging.getLogger(logger_name)
        self._entries: list = []  # In-memory audit log for querying

    def log(
        self,
        actor: str,
        action: AuditAction,
        resource_type: str,
        resource_id: Any,
        details: Any = None,
    ):
        """
        Log an audit event.
        
        Args:
            actor: Who performed the action (user ID, admin ID, etc.)
            action: What action was performed
            resource_type: Type of resource accessed
            resource_id: ID of the resource
            details: Optional non-sensitive details (str or dict)
        """
        import json as _json
        details_str = _json.dumps(details, ensure_ascii=False) if isinstance(details, dict) else (details or "")
        self._logger.info(
            "AUDIT: actor=%s action=%s resource_type=%s resource_id=%s details=%s",
            actor,
            action.value,
            resource_type,
            resource_id,
            redact_log_message(details_str),
        )
        # Store in-memory for querying
        self._entries.append({
            "actor": actor,
            "action": action.value,
            "resource_type": resource_type,
            "resource_id": str(resource_id),
            "details": redact_log_message(details_str),
            "timestamp": datetime.utcnow().isoformat(),
        })

    def query_logs(self, limit: int = 100, action: str = None) -> list:
        """Query recent audit log entries."""
        entries = self._entries
        if action:
            entries = [e for e in entries if e["action"] == action]
        return entries[-limit:]


# Global audit logger instance
audit_logger = AuditLogger()
