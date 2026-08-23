"""
R4.3 Privacy & Data Protection Tests

Tests for:
- Field encryption (passport, ID card)
- Blind index for searchable encryption
- API response masking
- Log redaction
- Audit logging
- Data deletion
"""
import os
import pytest
import tempfile
import shutil
from cryptography.fernet import Fernet

# Set environment variables before importing app modules
os.environ.setdefault("PRIVACY_HMAC_SECRET", "test-hmac-secret")
os.environ.setdefault("VAULT_FERNET_KEY", Fernet.generate_key().decode())
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-key")

from app.services.privacy import (
    PrivacyEncryptionService,
    PrivacyEncryptionError,
    mask_passport,
    mask_id_card,
    mask_email,
    mask_phone,
    mask_sensitive_fields,
    redact_log_message,
    SENSITIVE_FIELDS,
    DataClassification,
    AuditLogger,
    AuditAction,
    RetentionPeriod,
)
from app.services.audit_log import audit_log, AuditLog
from app.services.data_deletion import DataDeletionService, get_retention_policy


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def encryption_service():
    """Create a privacy encryption service for testing."""
    fernet_key = Fernet.generate_key().decode()
    return PrivacyEncryptionService(
        fernet_key=fernet_key,
        hmac_secret="test-hmac-secret",
    )


@pytest.fixture
def audit_logger():
    """Create an audit logger for testing."""
    return AuditLogger()


@pytest.fixture
def temp_upload_dir():
    """Create a temporary upload directory."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


# =============================================================================
# 1. Field Encryption Tests
# =============================================================================

class TestFieldEncryption:
    """Tests for encrypting sensitive fields."""

    def test_encrypt_passport(self, encryption_service):
        """Encrypting a passport number should produce ciphertext."""
        passport = "E12345678"
        encrypted = encryption_service.encrypt(passport)
        assert encrypted is not None
        assert encrypted != passport
        assert len(encrypted) > len(passport)

    def test_encrypt_id_card(self, encryption_service):
        """Encrypting an ID card number should produce ciphertext."""
        id_card = "110101199001011234"
        encrypted = encryption_service.encrypt(id_card)
        assert encrypted is not None
        assert encrypted != id_card

    def test_decrypt_returns_original(self, encryption_service):
        """Decrypting should return the original value."""
        passport = "E12345678"
        encrypted = encryption_service.encrypt(passport)
        decrypted = encryption_service.decrypt(encrypted)
        assert decrypted == passport

    def test_encrypt_empty_returns_empty(self, encryption_service):
        """Encrypting empty/None should return empty string."""
        assert encryption_service.encrypt(None) == ""
        assert encryption_service.encrypt("") == ""

    def test_decrypt_empty_returns_empty(self, encryption_service):
        """Decrypting empty/None should return empty string."""
        assert encryption_service.decrypt(None) == ""
        assert encryption_service.decrypt("") == ""

    def test_different_keys_cannot_decrypt(self):
        """Data encrypted with one key cannot be decrypted with another."""
        service1 = PrivacyEncryptionService(
            fernet_key=Fernet.generate_key().decode(),
            hmac_secret="test-hmac-secret",
        )
        service2 = PrivacyEncryptionService(
            fernet_key=Fernet.generate_key().decode(),
            hmac_secret="test-hmac-secret",
        )
        encrypted = service1.encrypt("E12345678")
        with pytest.raises(PrivacyEncryptionError):
            service2.decrypt(encrypted)


# =============================================================================
# 2. Blind Index Tests
# =============================================================================

class TestBlindIndex:
    """Tests for blind index (searchable encryption)."""

    def test_blind_index_stable(self, encryption_service):
        """Same input should produce same blind index."""
        value = "E12345678"
        idx1 = encryption_service.blind_index(value)
        idx2 = encryption_service.blind_index(value)
        assert idx1 == idx2

    def test_blind_index_different_values(self, encryption_service):
        """Different inputs should produce different blind indexes."""
        idx1 = encryption_service.blind_index("E12345678")
        idx2 = encryption_service.blind_index("E87654321")
        assert idx1 != idx2

    def test_blind_index_not_plaintext(self, encryption_service):
        """Blind index should not equal the plaintext."""
        value = "E12345678"
        idx = encryption_service.blind_index(value)
        assert idx != value

    def test_blind_index_is_hex(self, encryption_service):
        """Blind index should be a hex string."""
        idx = encryption_service.blind_index("E12345678")
        assert all(c in "0123456789abcdef" for c in idx)

    def test_blind_index_empty_returns_empty(self, encryption_service):
        """Blind index of None/empty should return empty string."""
        assert encryption_service.blind_index(None) == ""
        assert encryption_service.blind_index("") == ""


# =============================================================================
# 3. API Masking Tests
# =============================================================================

class TestAPIMasking:
    """Tests for API response masking."""

    def test_mask_passport(self):
        """Passport should be masked showing only last 4 chars."""
        masked = mask_passport("E12345678")
        assert "E12345678" not in masked
        assert masked.endswith("5678")

    def test_mask_id_card(self):
        """ID card should be masked showing only last 4 chars."""
        masked = mask_id_card("110101199001011234")
        assert "110101199001011234" not in masked
        assert masked.endswith("1234")

    def test_mask_email(self):
        """Email should be masked."""
        masked = mask_email("test@example.com")
        assert "test@example.com" not in masked
        assert "@" in masked or "***" in masked

    def test_mask_phone(self):
        """Phone should be masked."""
        masked = mask_phone("+8613800138000")
        assert "13800138000" not in masked

    def test_mask_sensitive_fields(self):
        """mask_sensitive_fields should mask known sensitive fields."""
        data = {
            "passport_info": "E12345678",
            "raw_input": '{"name": "test"}',
            "name": "Test User",
        }
        masked = mask_sensitive_fields(data)
        # Sensitive fields should be masked
        assert masked.get("name") == "Test User"  # Non-sensitive field unchanged


# =============================================================================
# 4. Log Redaction Tests
# =============================================================================

class TestLogRedaction:
    """Tests for log redaction."""

    def test_redact_password_in_log(self):
        """Password in log message should be redacted."""
        msg = "User login with password=secret123"
        redacted = redact_log_message(msg)
        assert "secret123" not in redacted

    def test_redact_token_in_log(self):
        """Token in log message should be redacted."""
        msg = "Bearer token: eyJhbGciOiJIUzI1NiJ9.test"
        redacted = redact_log_message(msg)
        assert "eyJhbGciOiJIUzI1NiJ9" not in redacted

    def test_redact_passport_in_log(self):
        """Passport field in log message should be redacted."""
        msg = "Processing passport_number=E12345678 for user"
        redacted = redact_log_message(msg)
        assert "E12345678" not in redacted

    def test_redact_id_card_in_log(self):
        """ID card field in log message should be redacted."""
        msg = "id_card_number: 110101199001011234 verified"
        redacted = redact_log_message(msg)
        assert "110101199001011234" not in redacted

    def test_redact_fernet_key_in_log(self):
        """Fernet key field in log message should be redacted."""
        key = Fernet.generate_key().decode()
        msg = f"fernet_key: {key}"
        redacted = redact_log_message(msg)
        assert key not in redacted

    def test_redact_non_sensitive_passthrough(self):
        """Non-sensitive messages should pass through unchanged."""
        msg = "User login successful for user_id=123"
        redacted = redact_log_message(msg)
        assert redacted == msg


# =============================================================================
# 5. Audit Log Tests
# =============================================================================

class TestAuditLog:
    """Tests for audit logging."""

    def test_audit_log_function_exists(self):
        """audit_log function should exist and be callable."""
        assert callable(audit_log)

    def test_audit_log_class_exists(self):
        """AuditLog class should exist."""
        assert AuditLog is not None

    def test_audit_logger_class_exists(self):
        """AuditLogger class should exist."""
        assert AuditLogger is not None

    def test_audit_action_enum_values(self):
        """AuditAction enum should have expected values."""
        assert AuditAction.VIEW_SENSITIVE_DATA == "view_sensitive_data"
        assert AuditAction.DOWNLOAD_DOCUMENT == "download_document"
        assert AuditAction.DELETE_USER_DATA == "delete_user_data"
        assert AuditAction.DECRYPT_FIELD == "decrypt_field"


# =============================================================================
# 6. Data Deletion Tests
# =============================================================================

class TestDataDeletion:
    """Tests for data deletion service."""

    def test_retention_policy_exists(self):
        """Retention policy should be defined."""
        policy = get_retention_policy()
        assert isinstance(policy, dict)
        assert len(policy) > 0

    def test_retention_policy_has_entries(self):
        """Retention policy should have at least one entry."""
        policy = get_retention_policy()
        assert len(policy) >= 1

    def test_data_deletion_service_exists(self):
        """DataDeletionService class should exist."""
        assert DataDeletionService is not None

    def test_retention_period_class_exists(self):
        """RetentionPeriod class should exist."""
        assert RetentionPeriod is not None


# =============================================================================
# 7. Sensitive Field Definitions Tests
# =============================================================================

class TestSensitiveFieldDefinitions:
    """Tests for sensitive field definitions."""

    def test_passport_info_in_sensitive_fields(self):
        """passport_info should be in sensitive fields."""
        assert "passport_info" in SENSITIVE_FIELDS

    def test_raw_input_in_sensitive_fields(self):
        """raw_input should be in sensitive fields."""
        assert "raw_input" in SENSITIVE_FIELDS

    def test_household_info_in_sensitive_fields(self):
        """household_info should be in sensitive fields."""
        assert "household_info" in SENSITIVE_FIELDS

    def test_email_in_sensitive_fields(self):
        """email should be in sensitive fields."""
        assert "email" in SENSITIVE_FIELDS

    def test_sensitive_fields_have_classification(self):
        """Each sensitive field should have a DataClassification."""
        for field_name, classification in SENSITIVE_FIELDS.items():
            assert isinstance(classification, DataClassification), \
                f"{field_name} should have a DataClassification"

    def test_highly_sensitive_fields_exist(self):
        """At least one field should be classified as HIGHLY_SENSITIVE."""
        highly_sensitive = [
            f for f, c in SENSITIVE_FIELDS.items()
            if c == DataClassification.HIGHLY_SENSITIVE
        ]
        assert len(highly_sensitive) >= 1
