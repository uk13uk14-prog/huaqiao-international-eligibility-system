"""R1 安全底座测试 - SaaS Pro"""
import os
import sys
import pytest
from unittest.mock import patch

# 确保可以导入 app 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Create all tables before tests and drop after."""
    from app.database import engine, Base
    # Import all models to ensure they are registered with Base
    from app.models import Tenant, User, AuthToken, MembershipPlan, Order, PaymentOrder  # noqa
    from app.models import RechargeCode, PermissionConfig, EligibilityRecord, University  # noqa
    from app.models import AdmissionSchedule, CustomerVault, ExpertConsultation  # noqa
    from app.models import ConsultationReportVersion, MemberTimelineReminder  # noqa
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


class TestBcryptPasswordHashing:
    def test_bcrypt_hash_and_verify(self):
        from app.services.security import hash_password, verify_password
        password = "test_password_123"
        hashed = hash_password(password)
        assert hashed.startswith("$2b$")
        assert verify_password(password, hashed)
        assert not verify_password("wrong_password", hashed)

    def test_each_hash_has_unique_salt(self):
        from app.services.security import hash_password
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        assert h1 != h2

    def test_legacy_hash_detection(self):
        from app.services.security import is_legacy_hash
        legacy = "a" * 64  # SHA256 hex digest
        assert is_legacy_hash(legacy)
        assert not is_legacy_hash("$2b$12$xyz")


class TestJWTTokenExpiration:
    def test_jwt_contains_exp_and_correct_ttl(self):
        from app.services.security import create_token, decode_token
        from app.database import SessionLocal
        from app.models import Tenant, User
        from app.services.security import hash_password

        db = SessionLocal()
        try:
            tenant = Tenant(name="Test JWT Tenant", tenant_type="personal")
            db.add(tenant)
            db.flush()
            user = User(tenant_id=tenant.id, email="jwt_test@example.com", name="JWT Test", password_hash=hash_password("test"))
            db.add(user)
            db.commit()
            db.refresh(user)

            token = create_token(db, user)
            payload = decode_token(token)
            assert "exp" in payload
            assert "sub" in payload
            assert payload["sub"] == str(user.id)

            expected_ttl = 120 * 60  # 120 minutes
            actual_ttl = payload["exp"] - payload["iat"]
            assert abs(actual_ttl - expected_ttl) < 5
        finally:
            db.rollback()
            db.close()

    def test_expired_token_rejected(self):
        from app.services.security import decode_token
        from app.database import SessionLocal
        from app.models import Tenant, User
        from app.services.security import hash_password
        import jwt
        from app.config import get_settings

        db = SessionLocal()
        try:
            tenant = Tenant(name="Test Exp Tenant", tenant_type="personal")
            db.add(tenant)
            db.flush()
            user = User(tenant_id=tenant.id, email="exp_test@example.com", name="Exp Test", password_hash=hash_password("test"))
            db.add(user)
            db.commit()
            db.refresh(user)

            settings = get_settings()
            expired_payload = {
                "sub": str(user.id),
                "email": user.email,
                "role": user.role,
                "tenant_id": user.tenant_id,
                "exp": 1000000,  # expired
                "iat": 999000,
            }
            expired_token = jwt.encode(expired_payload, settings.jwt_secret_key, algorithm="HS256")
            with pytest.raises(Exception):
                decode_token(expired_token)
        finally:
            db.rollback()
            db.close()

    def test_tampered_token_rejected(self):
        from app.services.security import create_token, decode_token
        from app.database import SessionLocal
        from app.models import Tenant, User
        from app.services.security import hash_password

        db = SessionLocal()
        try:
            tenant = Tenant(name="Test Tamper Tenant", tenant_type="personal")
            db.add(tenant)
            db.flush()
            user = User(tenant_id=tenant.id, email="tamper_test@example.com", name="Tamper Test", password_hash=hash_password("test"))
            db.add(user)
            db.commit()
            db.refresh(user)

            token = create_token(db, user)
            tampered = token[:-5] + "XXXXX"
            with pytest.raises(Exception):
                decode_token(tampered)
        finally:
            db.rollback()
            db.close()

    def test_wrong_secret_rejected(self):
        from app.services.security import create_token, decode_token
        from app.database import SessionLocal
        from app.models import Tenant, User
        from app.services.security import hash_password
        import jwt

        db = SessionLocal()
        try:
            tenant = Tenant(name="Test Secret Tenant", tenant_type="personal")
            db.add(tenant)
            db.flush()
            user = User(tenant_id=tenant.id, email="secret_test@example.com", name="Secret Test", password_hash=hash_password("test"))
            db.add(user)
            db.commit()
            db.refresh(user)

            token = create_token(db, user)
            wrong_payload = jwt.decode(token, options={"verify_signature": False})
            wrong_token = jwt.encode(wrong_payload, "wrong-secret-key", algorithm="HS256")
            with pytest.raises(Exception):
                decode_token(wrong_token)
        finally:
            db.rollback()
            db.close()


class TestVaultFailFast:
    def test_no_key_raises_error(self):
        from app.config import get_settings
        get_settings.cache_clear()
        with patch.dict(os.environ, {"VAULT_FERNET_KEY": ""}, clear=False):
            get_settings.cache_clear()
            from app.services.vault_crypto import VaultConfigError, encrypt_profile_json
            with pytest.raises(VaultConfigError):
                encrypt_profile_json({"test": "data"})
            get_settings.cache_clear()

    def test_valid_key_works(self):
        from app.config import get_settings
        get_settings.cache_clear()
        from app.services.vault_crypto import encrypt_profile_json, decrypt_profile_json
        plaintext = {"name": "张三", "id_number": "110101199001011234"}
        ciphertext = encrypt_profile_json(plaintext)
        assert ciphertext != str(plaintext)
        decrypted = decrypt_profile_json(ciphertext)
        assert decrypted == plaintext


class TestProductionConfigGate:
    def test_production_requires_jwt_secret(self):
        from app.config import Settings
        with patch.dict(os.environ, {"ENV": "production", "JWT_SECRET_KEY": "", "VAULT_FERNET_KEY": "x", "ADMIN_TOKEN": "x"}, clear=False):
            s = Settings()
            with pytest.raises(RuntimeError):
                s.validate_production_config()

    def test_production_requires_vault_key(self):
        from app.config import Settings
        with patch.dict(os.environ, {"ENV": "production", "JWT_SECRET_KEY": "x", "VAULT_FERNET_KEY": "", "ADMIN_TOKEN": "x"}, clear=False):
            s = Settings()
            with pytest.raises(RuntimeError):
                s.validate_production_config()

    def test_development_allows_defaults(self):
        from app.config import Settings
        with patch.dict(os.environ, {"ENV": "development", "JWT_SECRET_KEY": "dev-key", "VAULT_FERNET_KEY": ""}, clear=False):
            s = Settings()
            s.validate_production_config()  # should not raise
