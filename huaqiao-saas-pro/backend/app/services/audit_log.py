"""
R4.3-12: Audit Log Service

Records security-relevant events without logging sensitive payloads.
"""
import json
import logging
from datetime import datetime
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    """Security-relevant actions to audit."""
    # Data access
    VIEW_SENSITIVE_DATA = "view_sensitive_data"
    DOWNLOAD_DOCUMENT = "download_document"
    VIEW_USER_PROFILE = "view_user_profile"

    # Data modification
    MODIFY_ELIGIBILITY_RESULT = "modify_eligibility_result"
    UPDATE_USER_DATA = "update_user_data"

    # Data deletion
    DELETE_USER_DATA = "delete_user_data"
    DELETE_ELIGIBILITY_RECORD = "delete_eligibility_record"
    DELETE_UPLOADED_FILE = "delete_uploaded_file"
    ANONYMIZE_USER = "anonymize_user"

    # Authentication
    ADMIN_LOGIN = "admin_login"
    USER_LOGIN = "user_login"
    TOKEN_ISSUED = "token_issued"
    TOKEN_REVOKED = "token_revoked"

    # Privacy
    DATA_EXPORT_REQUEST = "data_export_request"
    DATA_DELETION_REQUEST = "data_deletion_request"


class AuditLog:
    """
    Audit logger that records security events without sensitive payloads.

    Each log entry contains:
    - actor: who performed the action
    - action: what was done
    - resource_type: type of resource affected
    - resource_id: identifier of the resource
    - timestamp: when it happened
    - metadata: additional non-sensitive context
    """

    @staticmethod
    def record(
        actor: str,
        action: AuditAction,
        resource_type: str,
        resource_id: str,
        metadata: Optional[dict] = None,
    ) -> dict:
        """
        Record an audit event.

        IMPORTANT: Do NOT include sensitive data in metadata.
        Sensitive data includes: passwords, tokens, passport numbers,
        ID card numbers, Fernet keys, API keys, payment secrets.
        """
        entry = {
            "actor": actor,
            "action": action.value if isinstance(action, AuditAction) else str(action),
            "resource_type": resource_type,
            "resource_id": str(resource_id),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "metadata": AuditLog._sanitize_metadata(metadata or {}),
        }

        # Log to audit logger (separate from application logs)
        audit_logger = logging.getLogger("audit")
        audit_logger.info(json.dumps(entry, ensure_ascii=False))

        return entry

    @staticmethod
    def _sanitize_metadata(metadata: dict) -> dict:
        """
        Remove sensitive fields from metadata before logging.

        This is a safety net - callers should not include sensitive data
        in the first place.
        """
        sensitive_keys = {
            "password", "token", "authorization", "secret",
            "passport_number", "id_card_number", "passport",
            "fernet_key", "api_key", "payment_key",
            "raw_input", "ssn", "credit_card",
        }

        sanitized = {}
        for key, value in metadata.items():
            if key.lower() in sensitive_keys:
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = AuditLog._sanitize_metadata(value)
            else:
                sanitized[key] = value

        return sanitized


def audit_log(
    actor: str,
    action: str,
    resource_type: str,
    resource_id: str,
    metadata: Optional[dict] = None,
) -> dict:
    """Convenience function for recording audit events."""
    return AuditLog.record(actor, action, resource_type, resource_id, metadata)
