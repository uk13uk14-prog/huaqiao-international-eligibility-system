"""Student CRM / Student 360 V2 tests (sqlite, no production DB)."""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta

from cryptography.fernet import Fernet

os.environ["JWT_SECRET_KEY"] = "test-jwt-key-student-crm-v1"
os.environ["VAULT_FERNET_KEY"] = Fernet.generate_key().decode()
os.environ["DATABASE_URL"] = "sqlite:///./test_student_crm_v1.db"
os.environ["ENV"] = "development"
os.environ["AI_API_KEY"] = ""

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient


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


def _create_student(client, headers, name: str | None = "学生甲"):
    profile = {}
    if name:
        profile = {"basic_info": {"chinese_name": name, "english_name": "Stu", "intended_entry_year": "2027"}}
    r = client.post("/api/students", json={"wizard": True, "profile": profile}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["id"], r.json()


def test_student_name_create_update_sync(client):
    mh, _, _ = _register_member(client)
    sid, body = _create_student(client, mh, name=None)
    assert "未命名" in (body.get("display_name") or "")
    r = client.patch(
        f"/api/students/{sid}/sections/basic_info",
        headers=mh,
        json={"data": {"chinese_name": "王小明", "english_name": "Ming"}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["display_name"] == "王小明"
    from app.services.student_profile import display_name_of, empty_profile

    p = empty_profile()
    p["basic_info"]["chinese_name"] = "a@b.com"
    # email-like values must not become the display name preference over empty real names
    # our resolver skips @ values
    assert "@" not in display_name_of(p) or display_name_of(p) == "未命名学生"
    assert display_name_of(p) == "未命名学生"


def test_student_list_and_360_crm(client):
    ah = _admin_headers(client)
    mh, _, _ = _register_member(client)
    sid, _ = _create_student(client, mh, name="赵丽")
    lst = client.get("/api/admin/v1/students", headers=ah)
    assert lst.status_code == 200, lst.text
    hit = next(s for s in lst.json()["students"] if s["id"] == sid)
    assert hit["display_name"] == "赵丽"
    assert "cipher_blob" not in hit
    assert "assignee_label" in hit
    assert "crm_stage" in hit
    s360 = client.get(f"/api/admin/v1/students/{sid}", headers=ah)
    assert s360.status_code == 200, s360.text
    d = s360.json()
    assert d["student_id"] == sid
    assert "crm" in d
    assert "ops_header" in d
    assert "cipher_blob" not in str(d)


def test_assignee_followup_next_action_ai_draft(client):
    ah = _admin_headers(client)
    mh, _, _ = _register_member(client)
    sid, _ = _create_student(client, mh, name="钱进")
    staff = client.get("/api/admin/v1/staff", headers=ah)
    assert staff.status_code == 200, staff.text
    admin_id = staff.json()["staff"][0]["id"]
    a1 = client.post(
        f"/api/admin/v1/students/{sid}/assign",
        headers=ah,
        json={"assignee_user_id": admin_id},
    )
    assert a1.status_code == 200, a1.text
    assert a1.json()["crm"]["assignee_user_id"] == admin_id
    a2 = client.post(
        f"/api/admin/v1/students/{sid}/assign",
        headers=ah,
        json={"assignee_user_id": None},
    )
    assert a2.status_code == 200, a2.text
    fu = client.post(
        f"/api/admin/v1/students/{sid}/follow-ups",
        headers=ah,
        json={"content": "已电话沟通", "next_action": "确认清华材料", "source": "HUMAN"},
    )
    assert fu.status_code == 200, fu.text
    assert fu.json()["follow_up"]["source"] == "HUMAN"
    patch = client.patch(
        f"/api/admin/v1/students/{sid}/crm",
        headers=ah,
        json={
            "crm_stage": "PLANNING",
            "next_action": "确认清华材料",
            "next_follow_up_at": (datetime.utcnow() + timedelta(days=3)).isoformat(),
        },
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["crm"]["crm_stage"] == "PLANNING"
    assert patch.json()["crm"]["next_action"] == "确认清华材料"
    drafts = client.post(f"/api/admin/v1/students/{sid}/ai-follow-up-drafts", headers=ah)
    assert drafts.status_code == 200, drafts.text
    assert drafts.json()["auto_send"] is False
    assert all(d["auto_send"] is False for d in drafts.json()["drafts"])
    assert all(d["source"] == "AI_ASSISTED" for d in drafts.json()["drafts"])

    sid2, _ = _create_student(client, mh, name="孙别")
    fus = client.get(f"/api/admin/v1/students/{sid}/follow-ups", headers=ah).json()["follow_ups"]
    assert all(f["student_id"] == sid for f in fus)
    fus2 = client.get(f"/api/admin/v1/students/{sid2}/follow-ups", headers=ah).json()["follow_ups"]
    assert all(f["student_id"] == sid2 for f in fus2)
    assert not any(f["student_id"] == sid for f in fus2)


def test_ai_context_privacy_and_dashboard(client):
    ah = _admin_headers(client)
    from app.services.admin_ai_expert import assert_ai_context_privacy, build_ai_context
    from app.services.student_profile import empty_profile

    profile = empty_profile()
    profile["basic_info"]["chinese_name"] = "周密"
    profile["identity"]["passport_number"] = "E12345678"
    ctx = build_ai_context(
        student_id=9,
        profile=profile,
        crm={
            "assignee_label": "Admin",
            "crm_stage": "PLANNING",
            "crm_stage_label": "规划中",
            "next_action": "补材料",
            "next_follow_up_at": None,
            "risk_level": "LOW",
        },
    )
    assert "E12345678" not in ctx
    assert "cipher_blob" not in ctx
    assert "PLANNING" in ctx or "规划中" in ctx
    assert_ai_context_privacy(ctx, profile)
    dash = client.get("/api/admin/v1/dashboard", headers=ah)
    assert dash.status_code == 200
    assert "crm_todos" in dash.json()
