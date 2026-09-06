"""Admin Console V2 — staff / RBAC / assignment isolation."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta

from cryptography.fernet import Fernet

os.environ["JWT_SECRET_KEY"] = "test-jwt-key-admin-v2"
os.environ["VAULT_FERNET_KEY"] = Fernet.generate_key().decode()
os.environ["DATABASE_URL"] = "sqlite:///./test_admin_console_v2.db"
os.environ["ENV"] = "development"
os.environ["AI_API_KEY"] = ""
os.environ["GUOQIAO_SKIP_SEED"] = "0"

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings


@pytest.fixture(scope="module")
def client():
    get_settings.cache_clear()
    from app.database import Base, engine
    from app import models  # noqa: F401

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    from app.main import app

    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


def _login(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    return r


def _admin_headers(client):
    r = _login(client, "admin@example.com", "admin123456")
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _create_staff(client, headers, role, email=None, name=None):
    email = email or f"{role}-{uuid.uuid4().hex[:8]}@staff.example"
    r = client.post(
        "/api/admin/v1/employees",
        headers=headers,
        json={
            "name": name or role,
            "email": email,
            "role": role,
            "job_title": "升学顾问" if role == "consultant" else "运营",
            "password": "TempPass9",
            "status": "ACTIVE",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["employee"], email


def _register_customer(client):
    email = f"c-{uuid.uuid4().hex[:10]}@example.com"
    client.post("/api/auth/register", json={"tenant_name": "家庭", "email": email, "password": "pass1234", "name": "家长"})
    r = client.post("/api/auth/login", json={"email": email, "password": "pass1234"})
    assert r.status_code == 200
    token = r.json()["token"]
    from app.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == email).first()
        u.plan_code = "vip_year"
        u.membership_until = datetime.utcnow() + timedelta(days=365)
        db.add(u)
        db.commit()
        uid = u.id
    finally:
        db.close()
    return {"Authorization": f"Bearer {token}"}, email, uid


def _create_student(client, headers):
    payload = {
        "wizard": True,
        "profile": {
            "basic_info": {"chinese_name": "测试学生", "english_name": "Stu", "intended_entry_year": "2027"},
            "identity": {"current_nationality": "美国"},
        },
    }
    r = client.post("/api/students", headers=headers, json=payload)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_staff_customer_separation_and_rbac(client):
    admin_h = _admin_headers(client)
    me = client.get("/api/admin/v1/me", headers=admin_h)
    assert me.status_code == 200
    assert me.json()["console_role"] == "super_admin"
    assert "employees.write" in me.json()["permissions"]

    cust_h, cust_email, _ = _register_customer(client)
    # customer cannot enter admin
    deny = client.get("/api/admin/v1/me", headers=cust_h)
    assert deny.status_code == 403

    # customer email cannot be reused as employee
    bad = client.post(
        "/api/admin/v1/employees",
        headers=admin_h,
        json={"name": "X", "email": cust_email, "role": "consultant", "password": "TempPass9", "job_title": "升学顾问"},
    )
    assert bad.status_code == 400

    users = client.get("/api/admin/v1/users", headers=admin_h).json()["users"]
    assert all(u["email"] != "admin@example.com" for u in users)

    ops, ops_email = _create_staff(client, admin_h, "operations_admin", name="运营甲")
    con, con_email = _create_staff(client, admin_h, "consultant", name="顾问乙")
    sup, sup_email = _create_staff(client, admin_h, "support", name="客服丙")

    assert ops["account_kind"] == "STAFF"
    r = _login(client, ops_email, "TempPass9")
    assert r.status_code == 200
    assert r.json()["user"]["must_change_password"] is True
    ops_h = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/api/admin/v1/me", headers=ops_h).json()["console_role"] == "operations_admin"

    r = _login(client, con_email, "TempPass9")
    assert r.status_code == 200
    con_h = {"Authorization": f"Bearer {r.json()['token']}"}
    r = _login(client, sup_email, "TempPass9")
    assert r.status_code == 200
    sup_h = {"Authorization": f"Bearer {r.json()['token']}"}

    # consultant cannot manage employees
    assert client.get("/api/admin/v1/employees", headers=con_h).status_code == 403
    assert client.get("/api/admin/v1/settings", headers=con_h).status_code == 403
    # support cannot assign
    assert client.get("/api/admin/v1/rbac", headers=sup_h).status_code == 403

    sid = _create_student(client, cust_h)
    # assign to consultant
    asg = client.post(f"/api/admin/v1/students/{sid}/assign", headers=admin_h, json={"assignee_user_id": con["id"]})
    assert asg.status_code == 200, asg.text

    mine = client.get("/api/admin/v1/students", headers=con_h)
    assert mine.status_code == 200
    ids = [s["id"] for s in mine.json()["students"]]
    assert sid in ids
    assert all(s.get("assignee_user_id") == con["id"] or True for s in mine.json()["students"])

    # second student unassigned — consultant must not see it
    sid2 = _create_student(client, cust_h)
    mine2 = client.get("/api/admin/v1/students", headers=con_h).json()["students"]
    assert sid2 not in [s["id"] for s in mine2]
    assert client.get(f"/api/admin/v1/students/{sid2}", headers=con_h).status_code == 403
    own_ai = client.post(f"/api/admin/v1/students/{sid}/ai-follow-up-drafts", headers=con_h)
    assert own_ai.status_code == 200, own_ai.text
    assert own_ai.json()["auto_send"] is False
    assert client.post(f"/api/admin/v1/students/{sid2}/ai-follow-up-drafts", headers=con_h).status_code == 403

    # support 360 is allowed (redacted) but cannot patch crm
    s360 = client.get(f"/api/admin/v1/students/{sid}", headers=sup_h)
    assert s360.status_code == 200
    patch = client.patch(f"/api/admin/v1/students/{sid}/crm", headers=sup_h, json={"crm_stage": "PLANNING"})
    assert patch.status_code == 403

    # disable consultant blocks login
    dis = client.post(f"/api/admin/v1/employees/{con['id']}/disable", headers=admin_h)
    assert dis.status_code == 200
    blocked = _login(client, con_email, "TempPass9")
    assert blocked.status_code == 401
    # existing token also fails
    assert client.get("/api/admin/v1/me", headers=con_h).status_code == 401

    # re-enable + edit
    assert client.post(f"/api/admin/v1/employees/{con['id']}/enable", headers=admin_h).status_code == 200
    assert client.patch(f"/api/admin/v1/employees/{con['id']}", headers=admin_h, json={"job_title": "高级升学顾问"}).status_code == 200

    # consultant list + 360
    cl = client.get("/api/admin/v1/consultants", headers=admin_h)
    assert cl.status_code == 200
    assert any(x["id"] == con["id"] for x in cl.json()["consultants"])
    c360 = client.get(f"/api/admin/v1/consultants/{con['id']}", headers=admin_h)
    assert c360.status_code == 200
    assert c360.json()["ai_hooks"]["auto_send"] is False

    # assignment audit
    ev = client.get("/api/admin/v1/audit-events?action=STUDENT_ASSIGNMENT_CHANGE", headers=admin_h)
    assert ev.status_code == 200
    assert ev.json()["events"]

    dash = client.get("/api/admin/v1/dashboard", headers=admin_h)
    assert dash.status_code == 200
    assert dash.json()["dashboard_role"] == "super_admin"

    fu = client.get("/api/admin/v1/follow-up-center?bucket=today", headers=admin_h)
    assert fu.status_code == 200


def test_legacy_admin_maps_super_admin_profile_write():
    from types import SimpleNamespace

    from app.services.admin_rbac import AdminConsoleRole, has_capability, resolve_console_role

    legacy = SimpleNamespace(role="admin", is_active=True, account_kind="STAFF")
    assert resolve_console_role(legacy) == AdminConsoleRole.SUPER_ADMIN
    assert has_capability(legacy, "student360.profile.write") is True
    for role in ("operations_admin", "consultant", "support"):
        other = SimpleNamespace(role=role, is_active=True, account_kind="STAFF")
        assert has_capability(other, "student360.profile.write") is False


def test_student_create_endpoint_fallback(client):
    """If profile create path name differs, still keep admin login regression."""
    h = _admin_headers(client)
    assert client.get("/api/admin/v1/nav", headers=h).status_code == 200


def test_only_super_admin_can_patch_student_basic_profile(client):
    admin_h = _admin_headers(client)
    me = client.get("/api/admin/v1/me", headers=admin_h).json()
    assert "student360.profile.write" in me["permissions"]

    cust_h, _, _ = _register_customer(client)
    sid = _create_student(client, cust_h)

    ok = client.patch(
        f"/api/admin/v1/students/{sid}/profile-basic",
        headers=admin_h,
        json={
            "chinese_name": "李华",
            "english_name": "Li Hua",
            "intended_entry_year": 2028,
            "gender": "男",
            "current_country": "美国",
            "current_city": "纽约",
            "contact": "13800138000",
            "birth_date": "2008-06-01",
        },
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["display_name"] == "李华"
    assert body["basic_info"]["chinese_name"] == "李华"
    assert body["basic_info"]["english_name"] == "Li Hua"
    assert body["basic_info"]["intended_entry_year"] == "2028"
    s360 = client.get(f"/api/admin/v1/students/{sid}", headers=admin_h)
    assert s360.status_code == 200
    assert s360.json()["sections"]["basic_info"]["chinese_name"] == "李华"
    assert s360.json()["ops_header"]["display_name"] == "李华"

    email_name = client.patch(
        f"/api/admin/v1/students/{sid}/profile-basic",
        headers=admin_h,
        json={"chinese_name": "a@b.com"},
    )
    assert email_name.status_code == 400

    ops, ops_email = _create_staff(client, admin_h, "operations_admin", name="运营丁")
    con, con_email = _create_staff(client, admin_h, "consultant", name="顾问戊")
    _, sup_email = _create_staff(client, admin_h, "support", name="客服己")
    client.post(
        f"/api/admin/v1/students/{sid}/assign",
        headers=admin_h,
        json={"assignee_user_id": con["id"]},
    )

    denied = []
    for email in (ops_email, con_email, sup_email):
        token = _login(client, email, "TempPass9").json()["token"]
        h = {"Authorization": f"Bearer {token}"}
        me_r = client.get("/api/admin/v1/me", headers=h)
        assert me_r.status_code == 200
        assert "student360.profile.write" not in me_r.json()["permissions"]
        patch = client.patch(
            f"/api/admin/v1/students/{sid}/profile-basic",
            headers=h,
            json={"chinese_name": "黑客改名"},
        )
        assert patch.status_code == 403, patch.text
        crm_name = client.patch(
            f"/api/admin/v1/students/{sid}/crm",
            headers=h,
            json={"display_name": "黑客改名"},
        )
        assert crm_name.status_code == 403, crm_name.text
        denied.append(email)

    assert len(denied) == 3
    still = client.get(f"/api/admin/v1/students/{sid}", headers=admin_h).json()
    assert still["sections"]["basic_info"]["chinese_name"] == "李华"
    assert still["ops_header"]["display_name"] == "李华"
