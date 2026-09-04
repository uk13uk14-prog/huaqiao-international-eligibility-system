"""Admin + AI Expert Console V1 Phase 3 tests."""
from __future__ import annotations

import ast
import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from cryptography.fernet import Fernet

os.environ["JWT_SECRET_KEY"] = "test-jwt-key-admin-v1-p3"
os.environ["VAULT_FERNET_KEY"] = Fernet.generate_key().decode()
os.environ["DATABASE_URL"] = "sqlite:///./test_admin_v1_p3.db"
os.environ["ENV"] = "development"
os.environ["AI_API_KEY"] = ""

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.admin_v1_api import ADMIN_V1_CONTRACT


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
    return r.json()["id"]


class TestContractAndAuth:
    def test_admin_api_contract(self, client):
        h = _admin_headers(client)
        r = client.get("/api/admin/v1/contract", headers=h)
        assert r.status_code == 200
        paths = r.json()["contract"]
        for required in ADMIN_V1_CONTRACT:
            assert required in paths
        # ADMIN_API_CONTRACT=PASS

    def test_admin_auth_required(self, client):
        assert client.get("/api/admin/v1/dashboard").status_code == 401
        # ADMIN_AUTH_REQUIRED=PASS

    def test_non_admin_denied(self, client):
        headers, _, _ = _register_member(client)
        assert client.get("/api/admin/v1/dashboard", headers=headers).status_code == 403
        # NON_ADMIN_DENIED=PASS


class TestStudent360:
    def test_student_360_and_privacy(self, client):
        h = _admin_headers(client)
        mh, _, _ = _register_member(client)
        sid = _create_student(client, mh, name="三百六十", passport="P99887766")
        r = client.get(f"/api/admin/v1/students/{sid}", headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["student_id"] == sid
        assert "cipher_blob" not in str(body)
        passport = body["sections"]["identity"].get("passport_info") or ""
        assert passport != "P99887766"
        assert "****" in passport or passport.endswith("7766")
        # STUDENT_360=PASS / RAW_CIPHER_NOT_EXPOSED=PASS / SENSITIVE masked

    def test_multi_student_isolation(self, client):
        h = _admin_headers(client)
        mh, _, _ = _register_member(client)
        s1 = _create_student(client, mh, name="隔离甲", passport="A11110001")
        s2 = _create_student(client, mh, name="隔离乙", passport="B22220002")
        r1 = client.get(f"/api/admin/v1/students/{s1}", headers=h).json()
        r2 = client.get(f"/api/admin/v1/students/{s2}", headers=h).json()
        assert r1["sections"]["basic_info"]["chinese_name"] == "隔离甲"
        assert r2["sections"]["basic_info"]["chinese_name"] == "隔离乙"
        # MULTI_STUDENT_ISOLATION=PASS

    def test_legacy_eligibility_not_guessed(self, client):
        h = _admin_headers(client)
        mh, _, uid = _register_member(client)
        s1 = _create_student(client, mh, name="资格甲")
        _create_student(client, mh, name="资格乙")
        from app.database import SessionLocal
        from app.models import EligibilityRecord, User

        db = SessionLocal()
        try:
            u = db.query(User).filter(User.id == uid).first()
            db.add(
                EligibilityRecord(
                    tenant_id=u.tenant_id,
                    user_id=uid,
                    student_id=None,
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
        # LEGACY_ELIGIBILITY_NOT_GUESSED=PASS


class TestAiPersistenceFlow:
    def test_draft_edit_approve_publish(self, client):
        h = _admin_headers(client)
        mh, _, _ = _register_member(client)
        s1 = _create_student(client, mh, name="AI甲", passport="C33330003")
        s2 = _create_student(client, mh, name="AI乙", passport="D44440004")

        # Create
        r = client.post(
            f"/api/admin/v1/students/{s1}/ai-drafts",
            headers=h,
            json={"report_kind": "student_portrait"},
        )
        assert r.status_code == 200, r.text
        draft = r.json()["draft"]
        assert draft["student_id"] == s1
        assert draft["status"] == "DRAFT"
        assert draft["published"] is False
        assert draft["auto_published"] is False
        assert draft["ai_provider"] == "LOCAL_TEMPLATE"
        assert "AI乙" not in (draft.get("raw_draft") or "")
        draft_id = draft["id"]
        # AI_DRAFT_CREATE=PASS / AI_CANNOT_AUTO_PUBLISH=PASS

        # List isolation
        listed = client.get(f"/api/admin/v1/students/{s2}/ai-drafts", headers=h).json()["drafts"]
        assert all(d["student_id"] == s2 for d in listed)
        assert listed == []

        # Edit
        er = client.patch(
            f"/api/admin/v1/students/{s1}/ai-drafts/{draft_id}",
            headers=h,
            json={"content": "STATUS=DRAFT\n顾问修订稿", "submit_review": True},
        )
        assert er.status_code == 200, er.text
        assert er.json()["draft"]["status"] == "REVIEWED"
        assert er.json()["draft"]["version_count"] >= 2
        # AI_DRAFT_EDIT=PASS

        # Student cannot see draft
        pub0 = client.get(f"/api/students/{s1}/published-consultations", headers=mh)
        assert pub0.status_code == 200
        assert pub0.json()["consultations"] == []
        # DRAFT_NOT_VISIBLE_TO_STUDENT=PASS

        # Approve
        ar = client.post(f"/api/admin/v1/students/{s1}/ai-drafts/{draft_id}/approve", headers=h)
        assert ar.status_code == 200
        assert ar.json()["draft"]["status"] == "APPROVED"
        assert ar.json()["draft"]["published"] is False
        # AI_APPROVE=PASS

        # Still not visible
        assert client.get(f"/api/students/{s1}/published-consultations", headers=mh).json()["consultations"] == []

        # Publish
        pr = client.post(f"/api/admin/v1/students/{s1}/ai-drafts/{draft_id}/publish", headers=h)
        assert pr.status_code == 200, pr.text
        assert pr.json()["draft"]["status"] == "PUBLISHED"
        # AI_PUBLISH=PASS

        # Owner sees published
        pub = client.get(f"/api/students/{s1}/published-consultations", headers=mh)
        assert pub.status_code == 200
        items = pub.json()["consultations"]
        assert len(items) == 1
        assert items[0]["status"] == "PUBLISHED"
        assert items[0]["student_id"] == s1
        assert "admin_note" not in items[0]
        assert "ai_provider" not in items[0]
        # PUBLISHED_VISIBLE_TO_OWNER_ONLY=PASS

        # Other student under same user sees none for s2
        assert client.get(f"/api/students/{s2}/published-consultations", headers=mh).json()["consultations"] == []

        # Cross-student publish denied
        r2 = client.post(
            f"/api/admin/v1/students/{s2}/ai-drafts",
            headers=h,
            json={"report_kind": "material_gaps"},
        )
        d2 = r2.json()["draft"]["id"]
        client.post(f"/api/admin/v1/students/{s2}/ai-drafts/{d2}/approve", headers=h)
        cross = client.post(f"/api/admin/v1/students/{s1}/ai-drafts/{d2}/publish", headers=h)
        assert cross.status_code in (404, 409)
        # CROSS_STUDENT_PUBLISH_DENIED=PASS

    def test_ai_context_privacy_minimized(self, client):
        from app.services.admin_ai_expert import assert_ai_context_privacy, build_ai_context

        profile = {
            "basic_info": {"chinese_name": "隐私", "current_country": "美国"},
            "identity": {
                "current_nationality": "美国",
                "passport_info": "SECRETPASS999",
                "id_card_number": "110101199001011234",
            },
            "courses": {"language_exams": [{"exam_type": "IELTS", "certificate_no": "CERTLEAK"}]},
            "education": {},
            "goals": {},
        }
        ctx = build_ai_context(student_id=42, profile=profile, timeline=[], eligibility={"mapping_status": "EMPTY"})
        assert_ai_context_privacy(ctx, profile)
        assert "SECRETPASS999" not in ctx
        assert "110101199001011234" not in ctx
        assert "CERTLEAK" not in ctx
        assert "student_id=42" in ctx
        # AI_CONTEXT_PRIVACY_MINIMIZED=PASS


class TestMigrationStatic:
    def test_migration_static_check(self):
        path = Path(__file__).resolve().parents[1] / "alembic" / "drafts" / "007_admin_ai_expert_v1_NOT_APPLIED.py"
        assert path.exists()
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
        # importable module check
        ns: dict = {}
        exec(compile(tree, str(path), "exec"), ns)
        assert ns["down_revision"] == "006_student_profile_slots"
        assert ns["revision"] == "007_admin_ai_expert_v1"
        assert "NOT APPLIED" in src or "NOT_APPLIED" in str(path)
        # upgrade must not drop existing business tables / rewrite data
        upgrade_fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "upgrade")
        upgrade_src = ast.get_source_segment(src, upgrade_fn) or ""
        assert "op.drop_table(" not in upgrade_src
        assert "op.drop_column(" not in upgrade_src
        assert "UPDATE " not in upgrade_src.upper() and "update(" not in upgrade_src.lower().replace(" ", "")
        assert "op.add_column" in upgrade_src
        assert "student_id" in src
        assert "audit_events" in src
        assert "payload_json" in src
        assert "drafts" in str(path)
        versions = Path(__file__).resolve().parents[1] / "alembic" / "versions"
        assert not any(versions.glob("007*"))
        # MIGRATION_STATIC_CHECK=PASS / MIGRATION_APPLIED=NO
