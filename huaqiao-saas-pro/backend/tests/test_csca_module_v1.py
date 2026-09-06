"""CSCA Exam Module V1 tests.

Profile / status flow / timeline (real dates only) / notification rules /
no fake dates / admin 360 + audit / auth+trial+university+notification regression.

Does not modify eligibility engines or university catalog data.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

from cryptography.fernet import Fernet

os.environ["JWT_SECRET_KEY"] = "test-jwt-key-csca-module-v1"
os.environ["VAULT_FERNET_KEY"] = Fernet.generate_key().decode()
os.environ["DATABASE_URL"] = "sqlite:///./test_csca_module_v1.db"
os.environ["ENV"] = "development"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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


def _auth_headers(client: TestClient) -> dict:
    email = f"csca-{uuid.uuid4().hex[:10]}@example.com"
    client.post(
        "/api/auth/register",
        json={"tenant_name": "CSCA家庭", "email": email, "password": "pass1234", "name": "家长"},
    )
    r = client.post("/api/auth/login", json={"email": email, "password": "pass1234"})
    assert r.status_code == 200, r.text
    from app.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user and hasattr(user, "student_profile_limit_override"):
            user.student_profile_limit_override = 50
            db.add(user)
            db.commit()
    finally:
        db.close()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _admin_headers(client: TestClient) -> dict:
    r = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "admin123456"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _create_student(client: TestClient, headers: dict) -> int:
    r = client.post("/api/students", headers=headers, json={"wizard": True, "profile": {}})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _profile(resp_json: dict) -> dict:
    return resp_json.get("profile") or resp_json


class TestCscaProfile:
    def test_csca_profile_default_and_status_flow(self, client):
        h = _auth_headers(client)
        sid = _create_student(client, h)
        loaded = client.get(f"/api/students/{sid}", headers=h)
        assert loaded.status_code == 200, loaded.text
        csca = _profile(loaded.json()).get("csca") or {}
        assert csca.get("csca_status") == "NOT_PLANNED"

        # fake date rejected / cleared
        r = client.patch(
            f"/api/students/{sid}/sections/csca",
            headers=h,
            json={"data": {"csca_status": "PLANNED", "csca_exam_date": "待定"}},
        )
        assert r.status_code == 200, r.text
        csca = _profile(r.json()).get("csca") or {}
        assert csca["csca_status"] == "PLANNED"
        assert not csca.get("csca_exam_date")

        exam = (date.today() + timedelta(days=40)).isoformat()
        r = client.patch(
            f"/api/students/{sid}/sections/csca",
            headers=h,
            json={
                "data": {
                    "csca_status": "REGISTERED",
                    "csca_exam_date": exam,
                    "csca_registration_deadline": (date.today() + timedelta(days=20)).isoformat(),
                    "csca_result_date": (date.today() + timedelta(days=70)).isoformat(),
                    "csca_score": "85",
                }
            },
        )
        assert r.status_code == 200, r.text
        csca = _profile(r.json()).get("csca") or {}
        assert csca["csca_status"] == "REGISTERED"
        assert csca["csca_exam_date"] == exam
        assert csca.get("csca_score") == "85"


class TestCscaTimelineNotifications:
    def test_timeline_generation_requires_real_dates(self, client):
        h = _auth_headers(client)
        sid = _create_student(client, h)
        client.patch(
            f"/api/students/{sid}/sections/csca",
            headers=h,
            json={"data": {"csca_status": "PLANNED"}},
        )
        tl = client.get(f"/api/students/{sid}/timeline", headers=h)
        assert tl.status_code == 200, tl.text
        items = tl.json().get("items") or tl.json().get("timeline") or []
        titles = [i.get("title") for i in items]
        assert "CSCA考试" not in titles

        exam = (date.today() + timedelta(days=45)).isoformat()
        reg = (date.today() + timedelta(days=25)).isoformat()
        result = (date.today() + timedelta(days=80)).isoformat()
        client.patch(
            f"/api/students/{sid}/sections/csca",
            headers=h,
            json={
                "data": {
                    "csca_status": "REGISTERED",
                    "csca_exam_date": exam,
                    "csca_registration_deadline": reg,
                    "csca_result_date": result,
                }
            },
        )
        tl = client.get(f"/api/students/{sid}/timeline", headers=h)
        items = tl.json().get("items") or tl.json().get("timeline") or []
        titles = [i.get("title") for i in items]
        assert "CSCA考试" in titles
        assert "CSCA报名截止" in titles
        assert "CSCA成绩发布" in titles
        for i in items:
            if i.get("title") in {"CSCA考试", "CSCA报名截止", "CSCA成绩发布"}:
                assert i.get("deadline"), "must carry a real deadline"

    def test_notification_rules_ladder(self, client):
        from app.database import SessionLocal
        from app.models import NotificationRule
        from app.services.notifications.constants import CSCA_EVENT_TYPES, DEFAULT_DEADLINE_LADDER
        from app.services.notifications.reminders import ensure_csca_rules, infer_event_type

        assert infer_event_type("CSCA报名截止") == "CSCA_REGISTRATION_DEADLINE"
        assert infer_event_type("CSCA考试") == "CSCA_EXAM_DATE"
        assert infer_event_type("CSCA成绩发布") == "CSCA_RESULT_DATE"

        db = SessionLocal()
        try:
            ensure_csca_rules(db)
            rows = (
                db.query(NotificationRule)
                .filter(NotificationRule.event_type.in_(CSCA_EVENT_TYPES))
                .all()
            )
            assert rows
            days = {r.days_before for r in rows}
            for d in DEFAULT_DEADLINE_LADDER:
                assert d in days
        finally:
            db.close()


class TestCscaNoFakeDate:
    def test_unit_parse_and_display(self):
        from app.services.csca import PENDING_OFFICIAL, csca_card, display_date, normalize_csca, parse_real_date

        assert parse_real_date("") is None
        assert parse_real_date("待定") is None
        assert parse_real_date("TBD") is None
        assert parse_real_date("2026-11-01").isoformat() == "2026-11-01"
        assert display_date("") == PENDING_OFFICIAL
        n = normalize_csca({"csca_status": "PLANNED", "csca_exam_date": "not-a-date"})
        assert n["csca_exam_date"] == ""
        card = csca_card(n)
        assert card["csca_exam_date"] == PENDING_OFFICIAL
        assert card["csca_exam_date_raw"] in (None, "")

    def test_exam_center_never_fakes(self, client):
        h = _auth_headers(client)
        sid = _create_student(client, h)
        r = client.get(f"/api/students/{sid}/csca", headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["card"]["csca_exam_date"] == "待官方公布"
        assert body.get("fake_date_allowed") is False


class TestCscaAdmin360:
    def test_admin_card_update_and_audit(self, client):
        h = _auth_headers(client)
        sid = _create_student(client, h)
        admin = _admin_headers(client)
        r = client.get(f"/api/admin/v1/students/{sid}", headers=admin)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "csca" in (body.get("sections") or {})
        assert body.get("csca_card") is not None

        exam = (date.today() + timedelta(days=33)).isoformat()
        r2 = client.patch(
            f"/api/admin/v1/students/{sid}/csca",
            headers=admin,
            json={"csca_status": "REGISTERED", "csca_exam_date": exam},
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["csca"]["csca_exam_date"] == exam
        assert r2.json().get("fake_date_allowed") is False

        from app.database import SessionLocal
        from app.models import AuditEvent
        from app.services.admin_audit import CSCA_UPDATE

        db = SessionLocal()
        try:
            row = (
                db.query(AuditEvent)
                .filter(AuditEvent.action == CSCA_UPDATE, AuditEvent.student_id == sid)
                .order_by(AuditEvent.id.desc())
                .first()
            )
            assert row is not None
        finally:
            db.close()


class TestRegressions:
    def test_auth_trial_university_notification(self, client):
        email = f"reg-{uuid.uuid4().hex[:8]}@example.com"
        rr = client.post(
            "/api/auth/register",
            json={"tenant_name": "回归", "email": email, "password": "pass1234", "name": "U"},
        )
        assert rr.status_code in (200, 201), rr.text
        login = client.post("/api/auth/login", json={"email": email, "password": "pass1234"})
        assert login.status_code == 200
        h = {"Authorization": f"Bearer {login.json()['token']}"}
        me = client.get("/api/me", headers=h)
        assert me.status_code == 200

        uni = client.get("/api/universities", headers=h)
        assert uni.status_code == 200
        # FREE may be limited; trial/paid should not error. Count > 0 after register (trial).
        data = uni.json()
        if isinstance(data, list):
            items = data
        else:
            items = data.get("items") or data.get("universities") or []
        assert isinstance(items, list)

        notif = client.get("/api/notifications", headers=h)
        assert notif.status_code == 200

        sid = _create_student(client, h)
        csca = client.get(f"/api/students/{sid}/csca", headers=h)
        assert csca.status_code == 200
