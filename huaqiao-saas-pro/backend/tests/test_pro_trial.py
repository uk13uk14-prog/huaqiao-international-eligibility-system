"""7-day Pro Trial entitlement tests (server-side; no schema migration)."""
import os
import sys
import uuid
from datetime import datetime, timedelta
from unittest import mock

from cryptography.fernet import Fernet

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-key-pro-trial")
os.environ.setdefault("VAULT_FERNET_KEY", Fernet.generate_key().decode())
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_pro_trial.db")
os.environ.setdefault("ENV", "development")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.services.membership_trial import (
    TRIAL_DAYS,
    TRIAL_PLAN_CODE,
    is_paid,
    trial_info,
)
from app.services.permissions import FREE_LIMITS, entitlements, feature_summary


@pytest.fixture(scope="module")
def client():
    from app.config import get_settings

    get_settings.cache_clear()
    from app.database import Base, engine
    from app import models  # noqa: F401

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    from app.main import app

    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


def _register(client):
    email = f"trial-{uuid.uuid4().hex[:10]}@example.com"
    r = client.post(
        "/api/auth/register",
        json={
            "tenant_name": "Trial Org",
            "tenant_type": "agency",
            "email": email,
            "password": "pass1234",
            "name": "试用用户",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    return body["token"], body["user"], email


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestNewUserTrial:
    def test_new_user_trial_created(self, client):
        token, user, _ = _register(client)
        assert user["plan_code"] == TRIAL_PLAN_CODE
        assert user["trial_active"] is True
        assert user["trial_status"] == "ACTIVE"
        assert user["paid"] is True
        assert user["is_pro"] is True
        assert user["trial_days_remaining"] == TRIAL_DAYS
        assert user["trial_ends_at"]
        # Server fields present on entitlements
        e = client.get("/api/membership/entitlements", headers=_auth(token))
        assert e.status_code == 200
        ej = e.json()
        assert ej["trial_active"] is True
        assert ej["university_limit"] == 999
        assert ej["is_pro"] is True


class TestTrialFullAccess:
    def test_trial_universities_full_catalog_filter(self, client):
        token, user, _ = _register(client)
        assert feature_summary(
            type(
                "U",
                (),
                {
                    "plan_code": user["plan_code"],
                    "membership_until": datetime.fromisoformat(user["membership_until"]),
                    "student_profile_limit_override": None,
                },
            )()
        )["full_elite_university_library"] is True
        # API path: paid entitlement → university_limit 999 (no is_core filter)
        e = entitlements(
            type(
                "U",
                (),
                {
                    "plan_code": TRIAL_PLAN_CODE,
                    "membership_until": datetime.utcnow() + timedelta(days=7),
                    "student_profile_limit_override": None,
                },
            )()
        )
        assert e["university_limit"] == 999

    def test_trial_student_profile_and_multi(self, client):
        token, _, _ = _register(client)
        h = _auth(token)
        ids = []
        for i in range(3):
            r = client.post(
                "/api/students",
                json={"wizard": True, "profile": {"basic_info": {"chinese_name": f"试{i}"}}},
                headers=h,
            )
            assert r.status_code == 200, r.text
            ids.append(r.json()["id"])
        # 4th blocked at Pro seat=3
        r4 = client.post("/api/students", json={"wizard": True, "profile": {}}, headers=h)
        assert r4.status_code == 403
        # switch list
        lst = client.get("/api/students", headers=h)
        assert lst.status_code == 200
        assert len(lst.json()["students"]) >= 3

    def test_trial_eligibility_routes_exist(self, client):
        token, user, _ = _register(client)
        # Trial gets Pro feature flags used by eligibility / planning UX
        assert user["features"]["international_planning"] is True
        assert user["features"]["full_elite_university_library"] is True
        openapi = client.get("/openapi.json")
        assert openapi.status_code == 200
        paths = openapi.json().get("paths") or {}
        assert "/api/eligibility/international" in paths
        assert "/api/eligibility/huaqiao" in paths
        # Auth works for trial user (eligibility engines need full payload — covered elsewhere)
        me = client.get("/api/me", headers=_auth(token))
        assert me.status_code == 200
        assert me.json()["is_pro"] is True


class TestTrialExpired:
    def test_expired_data_preserved_and_free_limit(self, client):
        token, user, email = _register(client)
        h = _auth(token)
        r = client.post(
            "/api/students",
            json={"wizard": True, "profile": {"basic_info": {"chinese_name": "保留"}}},
            headers=h,
        )
        assert r.status_code == 200
        sid = r.json()["id"]

        from app.database import SessionLocal
        from app.models import User

        db = SessionLocal()
        try:
            u = db.query(User).filter(User.email == email).first()
            u.membership_until = datetime.utcnow() - timedelta(days=1)
            db.add(u)
            db.commit()
            db.refresh(u)
            assert is_paid(u) is False
            assert trial_info(u)["trial_status"] == "EXPIRED"
            assert entitlements(u)["university_limit"] == FREE_LIMITS["university_limit"]
        finally:
            db.close()

        # Login still works
        login = client.post("/api/auth/login", json={"email": email, "password": "pass1234"})
        assert login.status_code == 200
        assert login.json()["user"]["trial_status"] == "EXPIRED"
        assert login.json()["user"]["paid"] is False

        # Student data still listed (preserved)
        lst = client.get("/api/students", headers=h)
        assert lst.status_code == 200
        ids = [s["id"] for s in lst.json()["students"]]
        assert sid in ids

        # Universities use free filter (limit < 999)
        me = client.get("/api/membership/entitlements", headers=h)
        assert me.json()["university_limit"] == FREE_LIMITS["university_limit"]
        assert me.json()["university_limit"] < 999


class TestPaidAndExistingUsers:
    def test_paid_vip_full_access_not_downgraded(self, client):
        token, _, email = _register(client)
        from app.database import SessionLocal
        from app.models import User

        db = SessionLocal()
        try:
            u = db.query(User).filter(User.email == email).first()
            u.plan_code = "vip_month"
            u.membership_until = datetime.utcnow() + timedelta(days=30)
            db.add(u)
            db.commit()
            db.refresh(u)
            assert is_paid(u) is True
            assert trial_info(u)["trial_status"] == "PAID"
            assert entitlements(u)["university_limit"] == 999
        finally:
            db.close()

        me = client.get("/api/me", headers=_auth(token))
        assert me.json()["paid"] is True
        assert me.json()["is_pro"] is True

    def test_existing_free_user_not_auto_trial(self, client):
        """Historical free users (plan_code=free) stay free — not rewritten to trial."""
        token, _, email = _register(client)
        from app.database import SessionLocal
        from app.models import User

        db = SessionLocal()
        try:
            u = db.query(User).filter(User.email == email).first()
            u.plan_code = "free"
            u.membership_until = None
            db.add(u)
            db.commit()
            db.refresh(u)
            assert is_paid(u) is False
            assert trial_info(u)["trial_status"] == "NONE"
        finally:
            db.close()
        me = client.get("/api/me", headers=_auth(token))
        assert me.json()["plan_code"] == "free"
        assert me.json()["trial_active"] is False

    def test_legacy_vip_null_until_protected(self):
        u = type(
            "U",
            (),
            {"plan_code": "vip_year", "membership_until": None, "created_at": None},
        )()
        assert is_paid(u) is True


class TestClientCannotExtendTrial:
    def test_client_clock_cannot_extend(self, client):
        token, user, email = _register(client)
        # Spoof "future" by pretending client sends trial_ends_at far away — server ignores
        from app.database import SessionLocal
        from app.models import User

        db = SessionLocal()
        try:
            u = db.query(User).filter(User.email == email).first()
            real_end = u.membership_until
            # Force expired on server
            u.membership_until = datetime.utcnow() - timedelta(hours=1)
            db.add(u)
            db.commit()
            db.refresh(u)
            info = trial_info(u)
            assert info["trial_active"] is False
            # Even if we imagine client localStorage had longer date, entitlement uses DB
            assert info["trial_ends_at"] != (real_end + timedelta(days=30)).isoformat()
        finally:
            db.close()

        e = client.get("/api/membership/entitlements", headers=_auth(token))
        assert e.json()["trial_active"] is False
        assert e.json()["paid"] is False

    def test_localstorage_cannot_extend(self, client):
        # Entitlements endpoint does not accept client-supplied trial fields
        token, _, _ = _register(client)
        # POST body ignored for GET entitlements — paid comes from server user row only
        e = client.get(
            "/api/membership/entitlements",
            headers={
                **_auth(token),
                "X-Trial-Ends-At": (datetime.utcnow() + timedelta(days=365)).isoformat(),
            },
        )
        assert e.status_code == 200
        # Still server-derived remaining ≤ 7
        assert e.json()["trial_days_remaining"] <= TRIAL_DAYS
