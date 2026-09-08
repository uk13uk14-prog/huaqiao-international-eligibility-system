"""Cooperation Center V1 — public read + admin CRUD / RBAC / upload."""
from __future__ import annotations

import os
import uuid
from io import BytesIO

from cryptography.fernet import Fernet

os.environ["JWT_SECRET_KEY"] = "test-jwt-key-cooperation-v1"
os.environ["VAULT_FERNET_KEY"] = Fernet.generate_key().decode()
os.environ["DATABASE_URL"] = "sqlite:///./test_cooperation_v1.db"
os.environ["ENV"] = "development"
os.environ["AI_API_KEY"] = ""
os.environ["GUOQIAO_SKIP_SEED"] = "0"

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    upload = tmp_path_factory.mktemp("coop_up")
    os.environ["COOPERATION_UPLOAD_DIR"] = str(upload)
    get_settings.cache_clear()
    from app.database import Base, engine
    from app import models  # noqa: F401

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    from app.main import app

    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)
    get_settings.cache_clear()


def _login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _admin_headers(client):
    r = _login(client, "admin@example.com", "admin123456")
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _create_staff(client, headers, role, email=None):
    email = email or f"{role}-{uuid.uuid4().hex[:8]}@staff.example"
    r = client.post(
        "/api/admin/v1/employees",
        headers=headers,
        json={
            "name": role,
            "email": email,
            "role": role,
            "job_title": "运营",
            "password": "TempPass9",
            "status": "ACTIVE",
        },
    )
    assert r.status_code == 200, r.text
    return email


def _staff_headers(client, email, password="TempPass9"):
    r = _login(client, email, password)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_public_api_default_and_hidden_fields(client):
    pub = client.get("/api/cooperation")
    assert pub.status_code == 200, pub.text
    body = pub.json()
    assert body["page_title"] == "合作中心"
    assert body["intro"] == ""
    assert body["contact"] == {}
    assert body["brands"] == []

    h = _admin_headers(client)
    patched = client.patch(
        "/api/admin/v1/cooperation/settings",
        headers=h,
        json={
            "page_title": "合作中心",
            "intro": "欢迎洽谈升学合作",
            "contact_name": "李顾问",
            "wechat": "gq_wechat_01",
            "phone": "13800138000",
            "email": "coop@example.com",
            "contact_note": "工作日 10:00-18:00",
            "show_contact_name": True,
            "show_wechat": True,
            "show_phone": False,
            "show_email": True,
            "show_contact_note": True,
            "show_qr": False,
        },
    )
    assert patched.status_code == 200, patched.text
    pub2 = client.get("/api/cooperation").json()
    assert pub2["intro"] == "欢迎洽谈升学合作"
    assert pub2["contact"]["contact_name"] == "李顾问"
    assert pub2["contact"]["wechat"] == "gq_wechat_01"
    assert pub2["contact"]["email"] == "coop@example.com"
    assert "phone" not in pub2["contact"]
    assert "qr_url" not in pub2["contact"]


def test_admin_rbac_and_menu(client):
    admin_h = _admin_headers(client)
    me = client.get("/api/admin/v1/me", headers=admin_h)
    assert me.status_code == 200
    assert "cooperation.read" in me.json()["permissions"]
    assert "cooperation.write" in me.json()["permissions"]
    assert any(i["path"] == "/cooperation" for i in me.json()["menu"])

    consultant_email = _create_staff(client, admin_h, "consultant")
    ch = _staff_headers(client, consultant_email)
    assert client.get("/api/admin/v1/cooperation/settings", headers=ch).status_code == 403
    assert client.post(
        "/api/admin/v1/cooperation/brands",
        headers=ch,
        json={"brand_name": "X"},
    ).status_code == 403
    assert client.get("/api/cooperation").status_code == 200


def test_admin_brand_crud_sort_visibility(client):
    h = _admin_headers(client)
    a = client.post(
        "/api/admin/v1/cooperation/brands",
        headers=h,
        json={"brand_name": "品牌甲", "description": "A", "sort_order": 20, "is_active": True},
    )
    b = client.post(
        "/api/admin/v1/cooperation/brands",
        headers=h,
        json={"brand_name": "品牌乙", "description": "B", "sort_order": 10, "is_active": True},
    )
    assert a.status_code == 200 and b.status_code == 200, a.text + b.text
    aid, bid = a.json()["id"], b.json()["id"]

    listed = client.get("/api/admin/v1/cooperation/brands", headers=h).json()["brands"]
    names = [x["brand_name"] for x in listed]
    assert "品牌甲" in names and "品牌乙" in names

    pub = client.get("/api/cooperation").json()["brands"]
    assert [x["brand_name"] for x in pub][:2] == ["品牌乙", "品牌甲"]

    edited = client.patch(
        f"/api/admin/v1/cooperation/brands/{aid}",
        headers=h,
        json={"description": "甲说明更新", "is_active": False},
    )
    assert edited.status_code == 200
    assert edited.json()["description"] == "甲说明更新"
    pub2 = {x["brand_name"] for x in client.get("/api/cooperation").json()["brands"]}
    assert "品牌甲" not in pub2
    assert "品牌乙" in pub2

    reordered = client.post(
        "/api/admin/v1/cooperation/brands/reorder",
        headers=h,
        json={"ids": [aid, bid]},
    )
    assert reordered.status_code == 200
    orders = {x["id"]: x["sort_order"] for x in reordered.json()["brands"]}
    assert orders[aid] < orders[bid]

    deleted = client.delete(f"/api/admin/v1/cooperation/brands/{bid}", headers=h)
    assert deleted.status_code == 200
    leftover = [x["id"] for x in client.get("/api/admin/v1/cooperation/brands", headers=h).json()["brands"]]
    assert bid not in leftover


def test_admin_upload_qr(client):
    h = _admin_headers(client)
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05"
        b"\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    r = client.post(
        "/api/admin/v1/cooperation/upload",
        headers=h,
        files={"file": ("qr.png", BytesIO(png), "image/png")},
    )
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    assert url.startswith("/api/cooperation/media/")
    media = client.get(url)
    assert media.status_code == 200
    assert media.content[:8] == b"\x89PNG\r\n\x1a\n"

    saved = client.patch(
        "/api/admin/v1/cooperation/settings",
        headers=h,
        json={"qr_image_url": url, "show_qr": True},
    )
    assert saved.status_code == 200
    assert client.get("/api/cooperation").json()["contact"]["qr_url"] == url

    deny = client.post(
        "/api/admin/v1/cooperation/upload",
        headers=h,
        files={"file": ("x.txt", BytesIO(b"hello"), "text/plain")},
    )
    assert deny.status_code == 400
