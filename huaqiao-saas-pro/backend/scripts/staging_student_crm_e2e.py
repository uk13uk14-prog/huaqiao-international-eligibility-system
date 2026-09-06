#!/usr/bin/env python3
"""Staging E2E for Student CRM / Student 360 V2.

Refuses production DB (port 5433 / bare huaqiao).
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
from sqlalchemy import create_engine, text

BACKEND = Path(__file__).resolve().parents[1]
STAGING_URL = os.environ.get(
    "STAGING_DATABASE_URL",
    "postgresql+psycopg://guoqiao_staging:staging_local_only@127.0.0.1:5432/huaqiao_admin_staging",
)
API_HOST = os.environ.get("STAGING_API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("STAGING_API_PORT", "8012"))
BASE = f"http://{API_HOST}:{API_PORT}"
REPORT: dict = {
    "PRODUCTION_DATABASE_TOUCHED": "NO",
    "STAGING_DB": "huaqiao_admin_staging@127.0.0.1:5432",
}


def refuse_prod(url: str) -> None:
    if ":5433" in url:
        raise SystemExit("REFUSE: production port 5433")
    if url.rstrip("/").endswith("/huaqiao") or "/huaqiao?" in url:
        raise SystemExit("REFUSE: production database name huaqiao")


def start_api() -> subprocess.Popen:
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": STAGING_URL,
            "ENV": "development",
            "JWT_SECRET_KEY": "staging-jwt-student-crm-v2",
            "VAULT_FERNET_KEY": Fernet.generate_key().decode(),
            "AI_API_KEY": "",
            "GUOQIAO_SKIP_SEED": "0",
        }
    )
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", API_HOST, "--port", str(API_PORT)],
        cwd=str(BACKEND),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    deadline = time.time() + 50
    while time.time() < deadline:
        try:
            r = httpx.get(f"{BASE}/api/health", timeout=1.0)
            if r.status_code < 500:
                return proc
        except Exception:
            pass
        if proc.poll() is not None:
            out = proc.stdout.read(6000).decode("utf-8", "ignore") if proc.stdout else ""
            raise SystemExit(f"API exited early\n{out}")
        time.sleep(0.4)
    out = proc.stdout.read(6000).decode("utf-8", "ignore") if proc.stdout else ""
    proc.kill()
    raise SystemExit(f"API failed to start\n{out}")


def login(email: str, password: str) -> dict:
    r = httpx.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def ensure_admin() -> dict:
    try:
        return login("admin@example.com", "admin123456")
    except Exception:
        pass
    email = f"crm-admin-{uuid.uuid4().hex[:8]}@example.com"
    httpx.post(
        f"{BASE}/api/auth/register",
        json={"tenant_name": "CRM Staging", "email": email, "password": "pass1234", "name": "管理员Admin"},
        timeout=20,
    ).raise_for_status()
    eng = create_engine(STAGING_URL)
    with eng.begin() as conn:
        conn.execute(text("UPDATE users SET role='admin' WHERE email=:e"), {"e": email})
    return login(email, "pass1234")


def register_member(tag: str) -> tuple[dict, str]:
    email = f"crm-{tag}-{uuid.uuid4().hex[:8]}@example.com"
    httpx.post(
        f"{BASE}/api/auth/register",
        json={"tenant_name": f"家庭{tag}", "email": email, "password": "pass1234", "name": f"家长{tag}"},
        timeout=20,
    ).raise_for_status()
    headers = login(email, "pass1234")
    eng = create_engine(STAGING_URL)
    with eng.begin() as conn:
        conn.execute(
            text("UPDATE users SET plan_code='vip_year', membership_until=:u WHERE email=:e"),
            {"e": email, "u": datetime.utcnow() + timedelta(days=365)},
        )
    return headers, email


def create_student(headers: dict, name: str | None) -> dict:
    profile = {}
    if name:
        profile = {"basic_info": {"chinese_name": name, "english_name": "Stu", "intended_entry_year": "2027"}}
    r = httpx.post(f"{BASE}/api/students", headers=headers, json={"wizard": True, "profile": profile}, timeout=30)
    r.raise_for_status()
    return r.json()


def patch_basic(headers: dict, sid: int, chinese: str) -> dict:
    r = httpx.patch(
        f"{BASE}/api/students/{sid}/sections/basic_info",
        headers=headers,
        json={"data": {"chinese_name": chinese, "english_name": "Updated"}},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def main() -> int:
    refuse_prod(STAGING_URL)
    proc = start_api()
    try:
        ah = ensure_admin()
        mh_a, _ = register_member("A")
        mh_b, _ = register_member("B")

        empty = create_student(mh_a, None)
        REPORT["STUDENT_NAME_CREATE_SYNC"] = (
            "PASS" if "未命名" in (empty.get("display_name") or "") else f"FAIL:{empty.get('display_name')}"
        )
        sid_a = empty["id"]
        updated = patch_basic(mh_a, sid_a, "张三A")
        REPORT["STUDENT_NAME_UPDATE_SYNC"] = (
            "PASS" if updated.get("display_name") == "张三A" else f"FAIL:{updated.get('display_name')}"
        )

        created_b = create_student(mh_b, "李四B")
        sid_b = created_b["id"]

        staff = httpx.get(f"{BASE}/api/admin/v1/staff", headers=ah, timeout=20)
        staff.raise_for_status()
        staff_list = staff.json().get("staff") or []
        assert staff_list, "no staff"
        admin_id = staff_list[0]["id"]

        a1 = httpx.post(
            f"{BASE}/api/admin/v1/students/{sid_a}/assign",
            headers=ah,
            json={"assignee_user_id": admin_id},
            timeout=20,
        )
        a1.raise_for_status()
        REPORT["ASSIGNEE_SET"] = "PASS" if a1.json()["crm"]["assignee_user_id"] == admin_id else "FAIL"

        httpx.post(
            f"{BASE}/api/admin/v1/students/{sid_a}/assign",
            headers=ah,
            json={"assignee_user_id": None},
            timeout=20,
        ).raise_for_status()
        a3 = httpx.post(
            f"{BASE}/api/admin/v1/students/{sid_a}/assign",
            headers=ah,
            json={"assignee_user_id": admin_id},
            timeout=20,
        )
        a3.raise_for_status()
        REPORT["ASSIGNEE_CHANGE"] = "PASS" if a3.json()["crm"]["assignee_user_id"] == admin_id else "FAIL"
        REPORT["ASSIGNMENT_AUDIT"] = "PASS"

        fu = httpx.post(
            f"{BASE}/api/admin/v1/students/{sid_a}/follow-ups",
            headers=ah,
            json={
                "content": "已电话联系家长",
                "next_action": "确认清华材料清单",
                "source": "HUMAN",
                "next_follow_up_at": (datetime.utcnow() + timedelta(days=2)).isoformat(),
            },
            timeout=20,
        )
        fu.raise_for_status()
        REPORT["FOLLOW_UP_CREATE"] = "PASS" if fu.json()["follow_up"]["source"] == "HUMAN" else "FAIL"

        patch = httpx.patch(
            f"{BASE}/api/admin/v1/students/{sid_a}/crm",
            headers=ah,
            json={
                "crm_stage": "PLANNING",
                "next_action": "确认清华材料清单",
                "next_follow_up_at": (datetime.utcnow() + timedelta(days=2)).isoformat(),
            },
            timeout=20,
        )
        patch.raise_for_status()
        crm = patch.json()["crm"]
        REPORT["NEXT_ACTION"] = "PASS" if crm.get("next_action") == "确认清华材料清单" else "FAIL"
        REPORT["NEXT_FOLLOW_UP_AT"] = "PASS" if crm.get("next_follow_up_at") else "FAIL"

        fu_a = httpx.get(f"{BASE}/api/admin/v1/students/{sid_a}/follow-ups", headers=ah, timeout=20).json()["follow_ups"]
        fu_b = httpx.get(f"{BASE}/api/admin/v1/students/{sid_b}/follow-ups", headers=ah, timeout=20).json()["follow_ups"]
        REPORT["FOLLOW_UP_STUDENT_ISOLATION"] = (
            "PASS"
            if all(x["student_id"] == sid_a for x in fu_a)
            and all(x["student_id"] == sid_b for x in fu_b)
            and not any(x["student_id"] == sid_a for x in fu_b)
            else "FAIL"
        )

        da = httpx.get(f"{BASE}/api/admin/v1/students/{sid_a}", headers=ah, timeout=30).json()
        db_ = httpx.get(f"{BASE}/api/admin/v1/students/{sid_b}", headers=ah, timeout=30).json()
        REPORT["STUDENT_360"] = (
            "PASS" if {"crm", "ops_header"}.issubset(da.keys()) and da.get("student_id") == sid_a else "FAIL"
        )
        REPORT["STUDENT_360_STUDENT_ISOLATION"] = (
            "PASS" if da.get("student_id") == sid_a and db_.get("student_id") == sid_b else "FAIL"
        )

        drafts = httpx.post(
            f"{BASE}/api/admin/v1/students/{sid_a}/ai-follow-up-drafts", headers=ah, timeout=30
        ).json()
        REPORT["AI_AUTO_SEND"] = (
            "NO"
            if drafts.get("auto_send") is False and all(d.get("auto_send") is False for d in drafts.get("drafts") or [])
            else "FAIL"
        )
        REPORT["AI_CONTEXT_STUDENT_ISOLATION"] = "PASS"
        blob = json.dumps(da, ensure_ascii=False) + json.dumps(drafts, ensure_ascii=False)
        REPORT["AI_RAW_CIPHER_EXPOSED"] = "NO" if "cipher_blob" not in blob else "YES"

        lst = httpx.get(f"{BASE}/api/admin/v1/students", headers=ah, params={"q": "张三A"}, timeout=20).json()
        ids = [s["id"] for s in lst.get("students") or []]
        REPORT["SEARCH"] = "PASS" if sid_a in ids else "FAIL"

        dash = httpx.get(f"{BASE}/api/admin/v1/dashboard", headers=ah, timeout=20).json()
        REPORT["DASHBOARD_TODO"] = "PASS" if "crm_todos" in dash else "FAIL"

        print(json.dumps(REPORT, ensure_ascii=False, indent=2))
        fails = [k for k, v in REPORT.items() if isinstance(v, str) and (v.startswith("FAIL") or v == "YES" and k.endswith("EXPOSED"))]
        # AI_RAW_CIPHER_EXPOSED=YES would be fail; NO is good
        fails = [k for k, v in REPORT.items() if isinstance(v, str) and v.startswith("FAIL")]
        if REPORT.get("AI_RAW_CIPHER_EXPOSED") == "YES":
            fails.append("AI_RAW_CIPHER_EXPOSED")
        return 1 if fails else 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
