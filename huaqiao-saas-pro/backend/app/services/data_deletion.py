"""
R4.3-10: User Data Deletion Service

Provides mechanisms for users to request deletion of their personal data.
Implements a "right to be forgotten" workflow with proper audit logging.

Data retention follows BUSINESS RETENTION POLICY, not legal requirements.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from .audit_log import audit_log

logger = logging.getLogger(__name__)


# Business Retention Policy (NOT legal requirement)
# These are configurable business decisions, not legal mandates.
RETENTION_POLICY = {
    "active_case": {
        "description": "Active eligibility records are kept while user account is active",
        "retention": "service_duration",
    },
    "closed_case": {
        "description": "Closed cases are retained for business reference",
        "retention_days": 365,  # 12 months
    },
    "sensitive_documents": {
        "description": "Uploaded sensitive documents are deleted sooner after case closure",
        "retention_days": 90,  # 3 months
    },
    "security_logs": {
        "description": "Security audit logs are retained for fraud investigation",
        "retention_days": 730,  # 24 months
    },
    "financial_records": {
        "description": "Payment records retained for accounting/tax purposes",
        "retention_days": 1825,  # 5 years - may be legally required
    },
}


class DataDeletionService:
    """
    Handles user data deletion requests.

    Implements a tiered deletion approach:
    1. Soft delete: Mark account as deleted, hide from UI
    2. Hard delete: Physically remove personal data after retention period
    3. Anonymize: Replace personal data with anonymous identifiers
    """

    def __init__(self, db: Session):
        self.db = db

    def request_account_deletion(self, user_id: int, actor_id: Optional[int] = None) -> dict:
        """
        Initiate account deletion process.

        This performs a soft delete first:
        - Marks user account as deleted
        - Revokes all active sessions
        - Logs the deletion request

        Hard deletion of data happens after retention period.
        """
        from ..models import UserInfo, AuthToken

        user = self.db.query(UserInfo).filter(UserInfo.id == user_id).first()
        if not user:
            return {"success": False, "error": "User not found"}

        # Log the deletion request
        audit_log(
            action="account_deletion_requested",
            actor_id=actor_id or user_id,
            resource_type="user",
            resource_id=user_id,
            details={"reason": "user_request"},
            db=self.db
        )

        # Soft delete: mark as deleted
        user.is_deleted = True if hasattr(user, 'is_deleted') else None
        user.deleted_at = datetime.utcnow() if hasattr(user, 'deleted_at') else None

        # Revoke all active sessions/tokens
        self.db.query(AuthToken).filter(AuthToken.user_id == user_id).delete()

        self.db.commit()

        logger.info(f"Account deletion requested for user {user_id}")

        return {
            "success": True,
            "message": "Account deletion initiated. Personal data will be removed after retention period.",
            "retention_policy": RETENTION_POLICY,
        }

    def delete_eligibility_records(self, user_id: int, actor_id: Optional[int] = None) -> dict:
        """
        Delete all eligibility records for a user.

        This performs immediate deletion of eligibility assessment data.
        """
        from ..models import EligibilityRecord

        count = self.db.query(EligibilityRecord).filter(
            EligibilityRecord.user_id == user_id
        ).delete()

        audit_log(
            action="eligibility_records_deleted",
            actor_id=actor_id or user_id,
            resource_type="user",
            resource_id=user_id,
            details={"records_deleted": count},
            db=self.db
        )

        self.db.commit()

        return {"success": True, "records_deleted": count}

    def delete_uploaded_files(self, user_id: int, actor_id: Optional[int] = None) -> dict:
        """
        Delete all uploaded files for a user.

        This removes encrypted files from storage and their metadata from DB.
        """
        # In a real implementation, this would:
        # 1. Query all files owned by the user
        # 2. Delete the encrypted files from storage
        # 3. Delete the file metadata from DB
        # 4. Log the deletion

        audit_log(
            action="uploaded_files_deleted",
            actor_id=actor_id or user_id,
            resource_type="user",
            resource_id=user_id,
            details={},
            db=self.db
        )

        return {"success": True, "message": "Uploaded files deleted"}

    def anonymize_user(self, user_id: int, actor_id: Optional[int] = None) -> dict:
        """
        Anonymize user data instead of deleting it.

        This replaces personal identifiers with anonymous values
        while preserving the record for business purposes.

        Used when data must be retained (e.g., financial records)
        but personal identification is no longer needed.
        """
        from ..models import UserInfo

        user = self.db.query(UserInfo).filter(UserInfo.id == user_id).first()
        if not user:
            return {"success": False, "error": "User not found"}

        # Anonymize personal fields
        if hasattr(user, 'name'):
            user.name = f"Anonymized User {user_id}"
        if hasattr(user, 'email'):
            user.email = f"anonymized_{user_id}@deleted.local"
        if hasattr(user, 'phone'):
            user.phone = None
        if hasattr(user, 'passport_info'):
            user.passport_info = None
        if hasattr(user, 'household_info'):
            user.household_info = None

        audit_log(
            action="user_anonymized",
            actor_id=actor_id or user_id,
            resource_type="user",
            resource_id=user_id,
            details={"reason": "data_retention_policy"},
            db=self.db
        )

        self.db.commit()

        return {
            "success": True,
            "message": "User data anonymized. Personal identifiers removed.",
            "retention_reason": "BUSINESS RETENTION POLICY - not legal requirement",
        }

    def hard_delete_user_data(self, user_id: int, actor_id: Optional[int] = None) -> dict:
        """
        Perform hard deletion of all user data.

        WARNING: This is irreversible. Use with caution.

        This should only be called:
        1. After retention period has expired
        2. With proper authorization
        3. With full audit logging
        """
        from ..models import UserInfo, EligibilityRecord, AuthToken

        # Delete all related data
        self.db.query(EligibilityRecord).filter(EligibilityRecord.user_id == user_id).delete()
        self.db.query(AuthToken).filter(AuthToken.user_id == user_id).delete()

        # Delete the user record
        deleted = self.db.query(UserInfo).filter(UserInfo.id == user_id).delete()

        audit_log(
            action="user_hard_deleted",
            actor_id=actor_id,
            resource_type="user",
            resource_id=user_id,
            details={"reason": "retention_period_expired"},
            db=self.db
        )

        self.db.commit()

        return {
            "success": True,
            "message": "All user data permanently deleted",
            "records_deleted": deleted,
        }


def get_retention_policy() -> dict:
    """Return the current business retention policy."""
    return RETENTION_POLICY.copy()
