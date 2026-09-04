"""Admin + AI Expert Console V1 API tests."""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta

from cryptography.fernet import Fernet

os.environ["JWT_SECRET_KEY"] = "test-jwt-key-admin-v1"
os.environ["VAULT_FERNET_KEY"] = Fernet.generate_key().decode()
os.environ["DATABASE_URL"] = "sqlite:///./test_admin_v1.db"
os.environ["ENV"] = "development"
os.environ["AI_API_KEY"] = ""  # force LOCAL_TEMPLATE

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.services.admin_ai_expert import clear_memory_for_tests


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
    clear_memory_for_tests()


@pytest.fixture(autouse=True)
def _clear_ai_mem():
    clear_memory_for_tests()
    yield
    clear_memory_for_tests()


def _admin_headers(client: TestClient) -> dict:
    r = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "admin123456"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _register_member(client: TestClient, plan="vip_year"):
    email = f"m-{uuid.uuid4().hex[:10]}@example.com"
    client.post(
        "/api/auth/register",
        json={"tenant_name": "家庭", "email": email, "password": "pass1234", "name": "家长"},
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
        user.membership_until = datetime.utcnow() + timedelta(days=365)
        db.add(user)
        db.commit()
        uid = user.id
    finally:
        db.close()
    return {"Authorization": f"Bearer {token}"}, email, uid


def _create_student(client, headers, name="学生甲", passport="E12345678"):
    payload = {
        "wizard": True,
        "profile": {
            "basic_info": {"chinese_name": name, "english_name": "Stu", "intended_entry_year": "2027"},
            "identity": {
                "current_nationality": "美国",
                "passport_info": passport,
                "id_card_number": "110101199001011234",
            },
            "education": {"current_school": {"school_name": "Demo High", "country": "美国"}},
            "goals": {"targets": [{"university_name": "清华", "priority_level": "reach"}]},
            "courses": {
                "language_exams": [{"exam_type": "TOEFL", "overall_score": "100", "certificate_no": "CERT999"}],
            },
        },
    }
    r = client.post("/api/students", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    sid = data.get("id") or (data.get("student") or {}).get("id") or data.get("student_id")
    assert sid, data
    return sid


def _student_id_from_create(resp_json):
    return resp_json.get("id") or (resp_json.get("student") or {}).get("id")


class TestAdminAuth:
    def test_admin_auth_required(self, client):
        r = client.get("/api/admin/v1/dashboard")
        assert r.status_code == 401
        # ADMIN_AUTH_REQUIRED=PASS

    def test_non_admin_denied(self, client):
        headers, _, _ = _register_member(client)
        r = client.get("/api/admin/v1/dashboard", headers=headers)
        assert r.status_code == 403
        # NON_ADMIN_DENIED=PASS

    def test_admin_can_login_me(self, client):
        h = _admin_headers(client)
        r = client.get("/api/admin/v1/me", headers=h)
        assert r.status_code == 200
        assert r.json()["console_role"] == "super_admin"


class TestAdminLists:
    def test_admin_user_list(self, client):
        h = _admin_headers(client)
        _register_member(client)
        r = client.get("/api/admin/v1/users", headers=h)
        assert r.status_code == 200
        assert r.json()["count"] >= 1
        assert "users" in r.json()
        # ADMIN_USER_LIST=PASS

    def test_admin_student_list(self, client):
        h = _admin_headers(client)
        mh, _, _ = _register_member(client)
        sid = _create_student(client, mh, name="列表学生")
        assert sid
        r = client.get("/api/admin/v1/students", headers=h)
        assert r.status_code == 200
        ids = [s["id"] for s in r.json()["students"]]
        assert sid in ids
        # ADMIN_STUDENT_LIST=PASS


class TestStudent360:
    def test_student_360(self, client):
        h = _admin_headers(client)
        mh, _, _ = _register_member(client)
        sid = _create_student(client, mh, name="三百六十", passport="P99887766")
        r = client.get(f"/api/admin/v1/students/{sid}", headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["student_id"] == sid
        assert "cipher_blob" not in str(body)
        assert body["sections"]["basic_info"]["chinese_name"] == "三百六十"
        # STUDENT_360=PASS
        # VAULT_RAW_CIPHER_NOT_EXPOSED=PASS
        passport = body["sections"]["identity"].get("passport_info") or ""
        assert passport != "P99887766"
        assert "****" in passport or passport.endswith("7766")
        # SENSITIVE_FIELDS_MASKED=PASS

    def test_student_id_isolation(self, client):
        h = _admin_headers(client)
        mh, _, _ = _register_member(client)
        s1 = _create_student(client, mh, name="隔离甲", passport="A11110001")
        s2 = _create_student(client, mh, name="隔离乙", passport="B22220002")
        r1 = client.get(f"/api/admin/v1/students/{s1}", headers=h)
        r2 = client.get(f"/api/admin/v1/students/{s2}", headers=h)
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()["sections"]["basic_info"]["chinese_name"] == "隔离甲"
        assert r2.json()["sections"]["basic_info"]["chinese_name"] == "隔离乙"
        assert r1.json()["student_id"] == s1
        assert r2.json()["student_id"] == s2
        # STUDENT_ID_ISOLATION=PASS
        # MULTI_STUDENT_NO_CROSS_LEAK=PASS

    def test_legacy_eligibility_unresolved(self, client):
        h = _admin_headers(client)
        mh, email, uid = _register_member(client)
        s1 = _create_student(client, mh, name="资格甲")
        s2 = _create_student(client, mh, name="资格乙")
        # Insert legacy eligibility on user_id only
        from app.database import SessionLocal
        from app.models import EligibilityRecord

        db = SessionLocal()
        try:
            from app.models import User

            u = db.query(User).filter(User.id == uid).first()
            db.add(
                EligibilityRecord(
                    tenant_id=u.tenant_id,
                    user_id=uid,
                    eligibility_type="international",
                    qualified=True,
                    conclusion="legacy",
                    raw_input='{"passport_info":"X99999999"}',
                )
            )
            db.commit()
        finally:
            db.close()

        r = client.get(f"/api/admin/v1/students/{s1}/eligibility", headers=h)
        assert r.status_code == 200
        assert r.json()["mapping_status"] == "UNRESOLVED"
        assert r.json()["records"] == []
        assert "尚未绑定" in r.json()["message"]
        # Same for sibling
        r2 = client.get(f"/api/admin/v1/students/{s2}/eligibility", headers=h)
        assert r2.json()["mapping_status"] == "UNRESOLVED"
        # LEGACY_ELIGIBILITY_UNRESOLVED=PASS


class TestAiExpert:
    def test_ai_context_single_student_and_draft_only(self, client):
        h = _admin_headers(client)
        mh, _, _ = _register_member(client)
        s1 = _create_student(client, mh, name="AI甲", passport="C33330003")
        s2 = _create_student(client, mh, name="AI乙", passport="D44440004")

        r = client.post(
            f"/api/admin/v1/students/{s1}/ai/generate",
            headers=h,
            json={"report_kind": "student_portrait"},
        )
        assert r.status_code == 200, r.text
        draft = r.json()["draft"]
        assert draft["student_id"] == s1
        assert draft["status"] == "DRAFT"
        assert draft["published"] is False
        assert draft["auto_published"] is False
        assert "AI乙" not in draft["content"]
        assert draft["ai_provider"] in ("LOCAL_TEMPLATE", "OPENAI_COMPATIBLE")
        # AI_CONTEXT_SINGLE_STUDENT_ONLY=PASS
        # AI_DRAFT_NOT_AUTO_PUBLISHED=PASS

        # Drafts for s2 must not include s1 draft
        r2 = client.get(f"/api/admin/v1/students/{s2}/ai/drafts", headers=h)
        assert r2.status_code == 200
        assert all(d["student_id"] == s2 for d in r2.json()["drafts"])
        assert r2.json()["drafts"] == []

        # Publish blocked
        approve = client.post(
            f"/api/admin/v1/students/{s1}/ai/drafts/{draft['id']}/approve",
            headers=h,
        )
        assert approve.status_code == 200
        assert approve.json()["draft"]["published"] is False
        pub = client.post(
            f"/api/admin/v1/students/{s1}/ai/drafts/{draft['id']}/publish",
            headers=h,
        )
        assert pub.status_code == 409
        assert "PUBLISH_BLOCKED" in pub.json()["detail"] or "student_id" in pub.json()["detail"]

    def test_dashboard(self, client):
        h = _admin_headers(client)
        r = client.get("/api/admin/v1/dashboard", headers=h)
        assert r.status_code == 200
        body = r.json()
        assert "total_users" in body
        assert "student_profiles" in body
