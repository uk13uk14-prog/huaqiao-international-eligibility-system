"""Student profile seat/slot limit tests."""
import os
import sys
import uuid
from datetime import datetime, timedelta

from cryptography.fernet import Fernet

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-key-student-slots")
os.environ.setdefault("VAULT_FERNET_KEY", Fernet.generate_key().decode())
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_student_slots.db")
os.environ.setdefault("ENV", "development")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.services.student_profile_entitlements import (
    FREE_STUDENT_PROFILE_LIMIT,
    LIMIT_REACHED_CODE,
    PRO_STUDENT_PROFILE_LIMIT,
    student_profile_entitlements,
)


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


def _register(client, plan="free", override=None):
    email = f"slots-{uuid.uuid4().hex[:10]}@example.com"
    client.post(
        "/api/auth/register",
        json={"tenant_name": "席位测试", "email": email, "password": "pass1234", "name": "顾问"},
    )
    r = client.post("/api/auth/login", json={"email": email, "password": "pass1234"})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    from app.database import SessionLocal
    from app.models import User
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        user.plan_code = plan
        if plan != "free":
            user.membership_until = datetime.utcnow() + timedelta(days=365)
        else:
            # Clear auto-granted trial so tests can force free tier
            user.membership_until = None
        user.student_profile_limit_override = override
        db.add(user)
        db.commit()
        uid = user.id
    finally:
        db.close()
    return {"Authorization": f"Bearer {token}"}, email, uid


class TestFreeLimit:
    def test_free_first_ok_second_blocked(self, client):
        headers, _, _ = _register(client, plan="free")
        r1 = client.post("/api/students", json={"wizard": True, "profile": {}}, headers=headers)
        assert r1.status_code == 200, r1.text
        assert r1.json()["slots"]["student_profile_limit"] == FREE_STUDENT_PROFILE_LIMIT
        assert r1.json()["slots"]["student_profile_used"] == 1
        r2 = client.post("/api/students", json={"wizard": True, "profile": {}}, headers=headers)
        assert r2.status_code == 403, r2.text
        detail = r2.json()["detail"]
        assert detail["code"] == LIMIT_REACHED_CODE
        assert detail["limit"] == 1
        assert detail["used"] == 1
        assert detail["remaining"] == 0


class TestProLimit:
    def test_pro_three_ok_fourth_blocked(self, client):
        headers, _, _ = _register(client, plan="pro_yearly")
        ids = []
        for i in range(3):
            r = client.post("/api/students", json={"wizard": True, "profile": {"basic_info": {"chinese_name": f"学生{i}"}}}, headers=headers)
            assert r.status_code == 200, r.text
            ids.append(r.json()["id"])
            assert r.json()["slots"]["student_profile_limit"] == PRO_STUDENT_PROFILE_LIMIT
        r4 = client.post("/api/students", json={"wizard": True, "profile": {}}, headers=headers)
        assert r4.status_code == 403
        assert r4.json()["detail"]["code"] == LIMIT_REACHED_CODE
        assert r4.json()["detail"]["used"] == 3
        # existing still editable
        patch = client.patch(
            f"/api/students/{ids[0]}/sections/basic_info",
            json={"data": {"chinese_name": "可编辑", "basic_info_notes": "ok"}},
            headers=headers,
        )
        assert patch.status_code == 200, patch.text
        assert patch.json()["profile"]["basic_info"]["chinese_name"] == "可编辑"


class TestSoftDeleteBypass:
    def test_soft_deleted_still_counts(self, client):
        headers, _, _ = _register(client, plan="free")
        created = client.post("/api/students", json={"wizard": True, "profile": {}}, headers=headers)
        sid = created.json()["id"]
        deleted = client.post(f"/api/students/{sid}/soft-delete", headers=headers)
        assert deleted.status_code == 200
        assert deleted.json()["status"] == "DELETED"
        assert deleted.json()["slots"]["student_profile_used"] == 1
        again = client.post("/api/students", json={"wizard": True, "profile": {}}, headers=headers)
        assert again.status_code == 403
        assert again.json()["detail"]["code"] == LIMIT_REACHED_CODE


class TestIsolationAndUpgradeDowngrade:
    def test_student_id_isolation(self, client):
        headers, _, _ = _register(client, plan="pro_yearly")
        a = client.post("/api/students", json={"wizard": True, "profile": {"basic_info": {"chinese_name": "甲"}}}, headers=headers).json()
        b = client.post("/api/students", json={"wizard": True, "profile": {"basic_info": {"chinese_name": "乙"}}}, headers=headers).json()
        client.patch(f"/api/students/{a['id']}/sections/basic_info", json={"data": {"chinese_name": "甲改", "basic_info_notes": "a"}}, headers=headers)
        client.patch(f"/api/students/{b['id']}/sections/basic_info", json={"data": {"chinese_name": "乙改", "basic_info_notes": "b"}}, headers=headers)
        ra = client.get(f"/api/students/{a['id']}", headers=headers).json()
        rb = client.get(f"/api/students/{b['id']}", headers=headers).json()
        assert ra["profile"]["basic_info"]["chinese_name"] == "甲改"
        assert rb["profile"]["basic_info"]["chinese_name"] == "乙改"
        assert ra["id"] != rb["id"]

    def test_free_to_pro_slots_increase(self, client):
        headers, email, uid = _register(client, plan="free")
        assert client.post("/api/students", json={"wizard": True, "profile": {}}, headers=headers).status_code == 200
        assert client.post("/api/students", json={"wizard": True, "profile": {}}, headers=headers).status_code == 403
        from app.database import SessionLocal
        from app.models import User
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == uid).first()
            user.plan_code = "pro_yearly"
            user.membership_until = datetime.utcnow() + timedelta(days=365)
            db.add(user)
            db.commit()
        finally:
            db.close()
        ent = client.get("/api/membership/entitlements", headers=headers)
        assert ent.status_code == 200
        body = ent.json()
        assert body["student_profile_limit"] == 3
        assert body["student_profile_used"] == 1
        assert body["student_profile_remaining"] == 2
        assert client.post("/api/students", json={"wizard": True, "profile": {}}, headers=headers).status_code == 200

    def test_pro_to_free_preserves_students(self, client):
        headers, email, uid = _register(client, plan="pro_yearly")
        ids = []
        for i in range(3):
            r = client.post("/api/students", json={"wizard": True, "profile": {"basic_info": {"chinese_name": f"S{i}"}}}, headers=headers)
            ids.append(r.json()["id"])
        from app.database import SessionLocal
        from app.models import User
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == uid).first()
            user.plan_code = "free"
            user.membership_until = None
            db.add(user)
            db.commit()
        finally:
            db.close()
        listed = client.get("/api/students", headers=headers)
        assert listed.status_code == 200
        assert len(listed.json()["students"]) == 3
        slots = listed.json()["slots"]
        assert slots["student_profile_limit"] == 1
        assert slots["student_profile_used"] == 3
        assert slots["student_profile_over_quota"] == 2
        assert slots["can_create_student"] is False
        # existing still readable
        one = client.get(f"/api/students/{ids[0]}", headers=headers)
        assert one.status_code == 200
        # create blocked
        assert client.post("/api/students", json={"wizard": True, "profile": {}}, headers=headers).status_code == 403


class TestAccountOverride:
    def test_override_covers_plan_limit(self, client):
        headers, email, uid = _register(client, plan="free", override=None)
        assert client.post("/api/students", json={"wizard": True, "profile": {}}, headers=headers).status_code == 200
        # admin override to 2
        from app.database import SessionLocal
        from app.models import User
        db = SessionLocal()
        try:
            admin = db.query(User).filter(User.email == "admin@example.com").first()
            assert admin is not None
            admin_id = admin.id
        finally:
            db.close()
        # login as admin
        admin_login = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "admin123456"})
        assert admin_login.status_code == 200
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['token']}"}
        ov = client.patch(
            f"/api/admin/users/{uid}/student-profile-limit",
            json={"student_profile_limit_override": 2},
            headers=admin_headers,
        )
        assert ov.status_code == 200, ov.text
        assert ov.json()["slots"]["student_profile_limit"] == 2
        assert client.post("/api/students", json={"wizard": True, "profile": {}}, headers=headers).status_code == 200
        assert client.post("/api/students", json={"wizard": True, "profile": {}}, headers=headers).status_code == 403


class TestEntitlementServiceDefaults:
    def test_defaults(self):
        assert FREE_STUDENT_PROFILE_LIMIT == 1
        assert PRO_STUDENT_PROFILE_LIMIT == 3
        assert student_profile_entitlements.resolve_limit(type("U", (), {"plan_code": "free", "student_profile_limit_override": None})()) == 1
        assert student_profile_entitlements.resolve_limit(type("U", (), {"plan_code": "vip_year", "student_profile_limit_override": None})()) == 3
        assert student_profile_entitlements.resolve_limit(type("U", (), {"plan_code": "free", "student_profile_limit_override": 10})()) == 10
