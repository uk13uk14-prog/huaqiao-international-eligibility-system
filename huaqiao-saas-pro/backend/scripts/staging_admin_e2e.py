#!/usr/bin/env python3
"""Staging E2E for Admin AI Expert V1 Phase 4.

Uses STAGING_DATABASE_URL only. Refuses port 5433 / bare DB huaqiao.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from cryptography.fernet import Fernet

BACKEND = Path(__file__).resolve().parents[1]
STAGING_URL = os.environ.get(
    "STAGING_DATABASE_URL",
    "postgresql+psycopg://guoqiao_staging:staging_local_only@127.0.0.1:5432/huaqiao_admin_staging",
)
API_HOST = os.environ.get("STAGING_API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("STAGING_API_PORT", "8011"))
BASE = f"http://{API_HOST}:{API_PORT}"

REPORT: dict = {"PRODUCTION_DATABASE_TOUCHED": "NO"}


def refuse_prod(url: str) -> None:
    if ":5433" in url:
        raise SystemExit("REFUSE: production port 5433")
    # bare /huaqiao (not huaqiao_admin_staging)
    if url.rstrip("/").endswith("/huaqiao") or "/huaqiao?" in url:
        raise SystemExit("REFUSE: production database name huaqiao")


def redact(url: str) -> str:
    import re

    return re.sub(r"://([^:/]+):([^@]+)@", r"://\1:***@", url)


def start_api() -> subprocess.Popen:
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": STAGING_URL,
            "ENV": "development",
            "JWT_SECRET_KEY": "staging-jwt-admin-ai-expert-v1",
            "VAULT_FERNET_KEY": Fernet.generate_key().decode(),
            "AI_API_KEY": "",
            "GUOQIAO_SKIP_SEED": "0",
            "ADMIN_TOKEN": "staging-admin-token-16chars",
        }
    )
    # Clear settings cache by fresh process
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            API_HOST,
            "--port",
            str(API_PORT),
        ],
        cwd=str(BACKEND),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    deadline = time.time() + 40
    while time.time() < deadline:
        try:
            r = httpx.get(f"{BASE}/api/health", timeout=1.0)
            if r.status_code < 500:
                break
        except Exception:
            pass
        if proc.poll() is not None:
            out = proc.stdout.read().decode() if proc.stdout else ""
            raise RuntimeError(f"API exited early:\n{out[-2000:]}")
        time.sleep(0.4)
    else:
        proc.kill()
        raise RuntimeError("API failed to start")
    return proc


def stop_api(proc: subprocess.Popen | None) -> None:
    if not proc:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def wait_health() -> None:
    for _ in range(50):
        try:
            httpx.get(f"{BASE}/api/health", timeout=1.0)
            return
        except Exception:
            time.sleep(0.2)


def main() -> int:
    refuse_prod(STAGING_URL)
    REPORT["STAGING_DATABASE_URL_REDACTED"] = redact(STAGING_URL)
    REPORT["STAGING_DB"] = "huaqiao_admin_staging@127.0.0.1:5432"

    client = httpx.Client(base_url=BASE, timeout=60.0)
    proc = None
    try:
        proc = start_api()
        wait_health()

        # --- Admin login (seed) ---
        admin = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "admin123456"})
        assert admin.status_code == 200, admin.text
        ah = {"Authorization": f"Bearer {admin.json()['token']}"}

        # --- Register member + 2 students ---
        email = f"stage-{uuid.uuid4().hex[:8]}@example.com"
        reg = client.post(
            "/api/auth/register",
            json={"tenant_name": "Staging家庭", "email": email, "password": "pass1234", "name": "Staging家长"},
        )
        assert reg.status_code == 200, reg.text
        login = client.post("/api/auth/login", json={"email": email, "password": "pass1234"})
        mh = {"Authorization": f"Bearer {login.json()['token']}"}

        # Force paid seats via DB
        from sqlalchemy import create_engine, text

        eng = create_engine(STAGING_URL)
        with eng.begin() as c:
            c.execute(
                text(
                    "UPDATE users SET plan_code='vip_year', membership_until=:u WHERE email=:e"
                ),
                {"u": datetime.utcnow() + timedelta(days=365), "e": email},
            )

        def create_student(name: str, passport: str) -> int:
            r = client.post(
                "/api/students",
                headers=mh,
                json={
                    "wizard": True,
                    "profile": {
                        "basic_info": {"chinese_name": name, "intended_entry_year": "2027"},
                        "identity": {"current_nationality": "美国", "passport_info": passport},
                        "education": {"current_school": {"school_name": f"{name}-School"}},
                        "goals": {"targets": [{"university_name": f"{name}-U", "priority_level": "target"}]},
                        "courses": {"language_exams": [{"exam_type": "TOEFL", "overall_score": "99", "certificate_no": f"C-{name}"}]},
                    },
                },
            )
            assert r.status_code == 200, r.text
            return r.json()["id"]

        sid_a = create_student("Staging学生A", "PA11111111")
        sid_b = create_student("Staging学生B", "PB22222222")
        assert sid_a != sid_b
        REPORT["FIXTURE_STUDENTS"] = {"A": sid_a, "B": sid_b}

        # Distinct eligibility fixtures (student-scoped)
        with eng.begin() as c:
            uid = c.execute(text("SELECT id, tenant_id FROM users WHERE email=:e"), {"e": email}).mappings().first()
            for sid, kind, concl in [
                (sid_a, "international", "A-intl-fixture"),
                (sid_b, "huaqiao", "B-hq-fixture"),
            ]:
                c.execute(
                    text(
                        """
                        INSERT INTO eligibility_records
                        (tenant_id, user_id, student_id, eligibility_type, qualified, conclusion, raw_input)
                        VALUES (:t,:u,:s,:k,true,:c,'{}')
                        """
                    ),
                    {"t": uid["tenant_id"], "u": uid["id"], "s": sid, "k": kind, "c": concl},
                )

        # Timeline items
        with eng.begin() as c:
            for sid, title in [(sid_a, "A-timeline"), (sid_b, "B-timeline")]:
                c.execute(
                    text(
                        """
                        INSERT INTO student_timeline_items
                        (student_id, user_id, tenant_id, title, status, is_manual)
                        VALUES (:s,:u,:t,:title,'NOT_STARTED',true)
                        """
                    ),
                    {"s": sid, "u": uid["id"], "t": uid["tenant_id"], "title": title},
                )

        # --- Admin E2E ---
        s360 = client.get(f"/api/admin/v1/students/{sid_a}", headers=ah)
        assert s360.status_code == 200, s360.text
        assert s360.json()["student_id"] == sid_a
        assert "cipher_blob" not in s360.text
        REPORT["STUDENT_360"] = "PASS"
        REPORT["ADMIN_E2E"] = "PASS"

        # AI generate
        gen = client.post(
            f"/api/admin/v1/students/{sid_a}/ai-drafts",
            headers=ah,
            json={"report_kind": "student_portrait"},
        )
        assert gen.status_code == 200, gen.text
        draft = gen.json()["draft"]
        assert draft["status"] == "DRAFT"
        assert draft["student_id"] == sid_a
        assert draft["auto_published"] is False
        draft_id = draft["id"]
        REPORT["AI_DRAFT"] = "PASS"

        # Edit
        edit = client.patch(
            f"/api/admin/v1/students/{sid_a}/ai-drafts/{draft_id}",
            headers=ah,
            json={"content": "STATUS=DRAFT\nStaging顾问编辑稿 for A only", "submit_review": True},
        )
        assert edit.status_code == 200, edit.text
        assert edit.json()["draft"]["status"] == "REVIEWED"
        REPORT["AI_EDIT"] = "PASS"

        # Non-published hidden from student
        pub0 = client.get(f"/api/students/{sid_a}/published-consultations", headers=mh)
        assert pub0.status_code == 200
        assert pub0.json()["consultations"] == []
        REPORT["NON_PUBLISHED_HIDDEN"] = "PASS"

        # Approve
        appr = client.post(f"/api/admin/v1/students/{sid_a}/ai-drafts/{draft_id}/approve", headers=ah)
        assert appr.status_code == 200
        assert appr.json()["draft"]["status"] == "APPROVED"
        assert appr.json()["draft"]["published"] is False
        REPORT["AI_APPROVE"] = "PASS"

        # Publish
        pub = client.post(f"/api/admin/v1/students/{sid_a}/ai-drafts/{draft_id}/publish", headers=ah)
        assert pub.status_code == 200, pub.text
        assert pub.json()["draft"]["status"] == "PUBLISHED"
        REPORT["AI_PUBLISH"] = "PASS"

        with eng.connect() as c:
            row = c.execute(
                text("SELECT student_id, status FROM expert_consultations WHERE id=:i"),
                {"i": draft_id},
            ).mappings().first()
            assert row["student_id"] == sid_a and row["status"] == "PUBLISHED"
            vcount = c.execute(
                text("SELECT count(*) FROM consultation_report_versions WHERE consultation_id=:i"),
                {"i": draft_id},
            ).scalar()
            assert vcount >= 3

        # Cross-student read denied
        cross_list = client.get(f"/api/admin/v1/students/{sid_b}/ai-drafts", headers=ah)
        assert cross_list.status_code == 200
        assert all(d["id"] != draft_id for d in cross_list.json()["drafts"])
        cross_get = client.get(f"/api/admin/v1/students/{sid_b}/consultations", headers=ah)
        body = cross_get.json()
        ids = [c.get("id") for c in (body.get("consultations") or [])]
        assert draft_id not in ids
        REPORT["CROSS_STUDENT_READ_DENIED"] = "PASS"

        # Cross-student publish denied
        gen_b = client.post(
            f"/api/admin/v1/students/{sid_b}/ai-drafts",
            headers=ah,
            json={"report_kind": "material_gaps"},
        )
        bid = gen_b.json()["draft"]["id"]
        client.post(f"/api/admin/v1/students/{sid_b}/ai-drafts/{bid}/approve", headers=ah)
        denied = client.post(f"/api/admin/v1/students/{sid_a}/ai-drafts/{bid}/publish", headers=ah)
        assert denied.status_code in (404, 409)
        REPORT["CROSS_STUDENT_PUBLISH_DENIED"] = "PASS"

        # Published owner API
        owned = client.get(f"/api/students/{sid_a}/published-consultations", headers=mh)
        assert owned.status_code == 200
        items = owned.json()["consultations"]
        assert len(items) == 1 and items[0]["status"] == "PUBLISHED" and items[0]["student_id"] == sid_a
        assert "admin_note" not in items[0] and "ai_provider" not in items[0]
        b_items = client.get(f"/api/students/{sid_b}/published-consultations", headers=mh).json()["consultations"]
        assert all(x["student_id"] == sid_b for x in b_items)
        assert all(x["id"] != draft_id for x in b_items)
        REPORT["PUBLISHED_OWNER_API"] = "PASS"

        # Audit events
        with eng.connect() as c:
            actions = [
                r[0]
                for r in c.execute(
                    text(
                        "SELECT action FROM audit_events WHERE student_id=:s ORDER BY id"
                    ),
                    {"s": sid_a},
                ).fetchall()
            ]
            for need in ("AI_GENERATE", "AI_EDIT", "AI_APPROVE", "AI_PUBLISH"):
                assert need in actions, actions
            metas = c.execute(
                text("SELECT metadata_json FROM audit_events WHERE student_id=:s"),
                {"s": sid_a},
            ).scalars().all()
            blob = "\n".join(metas or [])
            assert "PA11111111" not in blob
            assert "cipher" not in blob.lower()
        REPORT["AUDIT_EVENTS"] = "PASS"
        REPORT["PRIVACY_SCRUB"] = "PASS"

        # Restart persistence
        stop_api(proc)
        proc = None
        time.sleep(1)
        proc = start_api()
        wait_health()
        admin2 = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "admin123456"})
        ah2 = {"Authorization": f"Bearer {admin2.json()['token']}"}
        login2 = client.post("/api/auth/login", json={"email": email, "password": "pass1234"})
        mh2 = {"Authorization": f"Bearer {login2.json()['token']}"}
        again = client.get(f"/api/admin/v1/students/{sid_a}/ai-drafts", headers=ah2)
        assert again.status_code == 200
        found = [d for d in again.json()["drafts"] if d["id"] == draft_id]
        assert found and found[0]["status"] == "PUBLISHED"
        owned2 = client.get(f"/api/students/{sid_a}/published-consultations", headers=mh2)
        assert len(owned2.json()["consultations"]) == 1
        with eng.connect() as c:
            assert c.execute(text("SELECT count(*) FROM audit_events WHERE student_id=:s"), {"s": sid_a}).scalar() >= 4
            assert c.execute(
                text("SELECT count(*) FROM consultation_report_versions WHERE consultation_id=:i"),
                {"i": draft_id},
            ).scalar() >= 3
        REPORT["PERSISTENCE_AFTER_RESTART"] = "PASS"

        print(json.dumps(REPORT, ensure_ascii=False, indent=2))
        print("ALL_STAGING_E2E=PASS")
        return 0
    finally:
        stop_api(proc)
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
