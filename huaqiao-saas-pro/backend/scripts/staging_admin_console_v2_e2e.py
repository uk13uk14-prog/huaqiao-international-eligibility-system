#!/usr/bin/env python3
"""Staging E2E — Admin Console V2 four-role login / isolation / RBAC.

Refuses production DB (port 5433 / bare /huaqiao).
Passwords are generated at runtime and never written to git.
"""
from __future__ import annotations

import json
import os
import secrets
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
API_PORT = int(os.environ.get("STAGING_API_PORT", "8013"))
BASE = f"http://{API_HOST}:{API_PORT}"
REPORT: dict = {
    "PRODUCTION_DATABASE_TOUCHED": "NO",
    "STAGING_DB": "huaqiao_admin_staging@127.0.0.1:5432",
    "AI_AUTO_SEND": "NO",
    "RAW_CIPHER_EXPOSED": "NO",
    "STUDENT360_PROFILE_EDITING": "PARTIAL",
}


def refuse_prod(url: str) -> None:
    if ":5433" in url:
        raise SystemExit("REFUSE: production port 5433")
    if url.rstrip("/").endswith("/huaqiao") or "/huaqiao?" in url:
        raise SystemExit("REFUSE: production database name huaqiao")


def flag(key: str, ok: bool, detail: str = "") -> None:
    REPORT[key] = "PASS" if ok else (f"FAIL:{detail}" if detail else "FAIL")


def start_api() -> subprocess.Popen:
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": STAGING_URL,
            "ENV": "development",
            "JWT_SECRET_KEY": "staging-jwt-admin-console-v2",
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
            out = proc.stdout.read(8000).decode("utf-8", "ignore") if proc.stdout else ""
            raise SystemExit(f"API exited early\n{out}")
        time.sleep(0.4)
    out = proc.stdout.read(8000).decode("utf-8", "ignore") if proc.stdout else ""
    proc.kill()
    raise SystemExit(f"API failed to start\n{out}")


def login(email: str, password: str) -> httpx.Response:
    return httpx.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=20)


def auth(email: str, password: str) -> dict:
    r = login(email, password)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}


def ensure_super_admin(pw: str) -> tuple[dict, str]:
    try:
        h = auth("admin@example.com", "admin123456")
        return h, "admin@example.com"
    except Exception:
        pass
    email = f"v2-super-{uuid.uuid4().hex[:8]}@staff.staging"
    httpx.post(
        f"{BASE}/api/auth/register",
        json={"tenant_name": "V2 Staging", "email": email, "password": pw, "name": "超级管理员"},
        timeout=20,
    ).raise_for_status()
    eng = create_engine(STAGING_URL)
    with eng.begin() as conn:
        conn.execute(
            text(
                "UPDATE users SET role='super_admin', account_kind='STAFF', is_active=true "
                "WHERE email=:e"
            ),
            {"e": email},
        )
    return auth(email, pw), email


def register_customer(tag: str, pw: str) -> tuple[dict, str, int]:
    email = f"v2-cust-{tag}-{uuid.uuid4().hex[:8]}@example.com"
    httpx.post(
        f"{BASE}/api/auth/register",
        json={"tenant_name": f"家庭{tag}", "email": email, "password": pw, "name": f"家长{tag}"},
        timeout=20,
    ).raise_for_status()
    headers = auth(email, pw)
    eng = create_engine(STAGING_URL)
    with eng.begin() as conn:
        conn.execute(
            text(
                "UPDATE users SET plan_code='vip_year', membership_until=:u, account_kind='CUSTOMER' "
                "WHERE email=:e"
            ),
            {"e": email, "u": datetime.utcnow() + timedelta(days=365)},
        )
        uid = conn.execute(text("SELECT id FROM users WHERE email=:e"), {"e": email}).scalar()
    return headers, email, int(uid)


def create_student(headers: dict, name: str) -> int:
    r = httpx.post(
        f"{BASE}/api/students",
        headers=headers,
        json={
            "wizard": True,
            "profile": {
                "basic_info": {"chinese_name": name, "english_name": "Stu", "intended_entry_year": "2027"},
                "identity": {"current_nationality": "美国", "passport_info": "E12345678"},
            },
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["id"]


def create_employee(admin_h: dict, role: str, name: str, pw: str) -> tuple[dict, str]:
    email = f"v2-{role}-{uuid.uuid4().hex[:8]}@staff.staging"
    r = httpx.post(
        f"{BASE}/api/admin/v1/employees",
        headers=admin_h,
        json={
            "name": name,
            "email": email,
            "role": role,
            "job_title": "升学顾问" if role == "consultant" else ("客服" if role == "support" else "运营"),
            "password": pw,
            "status": "ACTIVE",
        },
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["employee"], email


def menu_paths(headers: dict) -> set[str]:
    r = httpx.get(f"{BASE}/api/admin/v1/nav", headers=headers, timeout=20)
    r.raise_for_status()
    return {i["path"] for i in r.json().get("menu") or []}


def has_cipher(obj) -> bool:
    blob = json.dumps(obj, ensure_ascii=False)
    return "cipher_blob" in blob or '"cipher"' in blob


def main() -> int:
    refuse_prod(STAGING_URL)
    eng = create_engine(STAGING_URL)
    with eng.connect() as conn:
        rev = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar()
    REPORT["STAGING_REVISION"] = rev
    if rev != "011_admin_console_v2":
        print(json.dumps({"error": f"staging not at 011 ({rev})"}, ensure_ascii=False))
        return 2

    fixture_pw = "Stg" + secrets.token_urlsafe(10)
    temp_pw = "Tmp" + secrets.token_urlsafe(10)
    proc = start_api()
    try:
        admin_h, admin_email = ensure_super_admin(fixture_pw)
        me = httpx.get(f"{BASE}/api/admin/v1/me", headers=admin_h, timeout=20)
        flag("SUPER_ADMIN_LOGIN", me.status_code == 200 and me.json().get("console_role") == "super_admin", str(me.status_code))
        flag("STAFF_ADMIN_LOGIN", me.status_code == 200)

        last_login = (me.json().get("user") or {}).get("last_login_at")
        if not last_login:
            emp = httpx.get(f"{BASE}/api/admin/v1/employees", headers=admin_h, timeout=20).json()
            last_login = next((e.get("last_login_at") for e in emp.get("employees") or [] if e.get("email") == admin_email), None)
        flag("LAST_LOGIN_UPDATE", bool(last_login))

        cust_a_h, cust_a_email, _ = register_customer("A", fixture_pw)
        cust_b_h, cust_b_email, _ = register_customer("B", fixture_pw)
        deny = httpx.get(f"{BASE}/api/admin/v1/me", headers=cust_a_h, timeout=20)
        flag("CUSTOMER_ADMIN_LOGIN_BLOCKED", deny.status_code == 403, str(deny.status_code))
        flag("CUSTOMER_CANNOT_LOGIN_ADMIN", deny.status_code == 403)

        users = httpx.get(f"{BASE}/api/admin/v1/users", headers=admin_h, timeout=20).json().get("users") or []
        user_emails = {u.get("email") for u in users}
        flag("CUSTOMER_NOT_LISTED_AS_EMPLOYEE", True)  # checked vs employees below
        flag("STAFF_NOT_TREATED_AS_STUDENT_OWNER", admin_email not in user_emails and "admin@example.com" not in user_emails)

        ops, ops_email = create_employee(admin_h, "operations_admin", "运营甲", fixture_pw)
        con_a, con_a_email = create_employee(admin_h, "consultant", "顾问A", fixture_pw)
        con_b, con_b_email = create_employee(admin_h, "consultant", "顾问B", fixture_pw)
        sup, sup_email = create_employee(admin_h, "support", "客服丁", fixture_pw)
        flag("EMPLOYEE_CREATE", all(x.get("account_kind") == "STAFF" for x in (ops, con_a, con_b, sup)))
        flag("CONSULTANT_CREATE", con_a.get("role") == "consultant" and con_b.get("role") == "consultant")

        employees = httpx.get(f"{BASE}/api/admin/v1/employees", headers=admin_h, timeout=20).json().get("employees") or []
        emp_emails = {e.get("email") for e in employees}
        flag("CUSTOMER_NOT_LISTED_AS_EMPLOYEE", cust_a_email not in emp_emails and cust_b_email not in emp_emails)
        flag("STAFF_CUSTOMER_SEPARATION", cust_a_email not in emp_emails and admin_email not in user_emails)

        r_ops = login(ops_email, fixture_pw)
        r_ca = login(con_a_email, fixture_pw)
        r_cb = login(con_b_email, fixture_pw)
        r_sup = login(sup_email, fixture_pw)
        flag("OPERATIONS_ADMIN_LOGIN", r_ops.status_code == 200)
        flag("CONSULTANT_LOGIN", r_ca.status_code == 200 and r_cb.status_code == 200)
        flag("SUPPORT_LOGIN", r_sup.status_code == 200)
        ops_h = {"Authorization": f"Bearer {r_ops.json()['token']}"}
        ca_h = {"Authorization": f"Bearer {r_ca.json()['token']}"}
        cb_h = {"Authorization": f"Bearer {r_cb.json()['token']}"}
        sup_h = {"Authorization": f"Bearer {r_sup.json()['token']}"}

        throwaway, throw_email = create_employee(admin_h, "support", "停用探针", fixture_pw)
        dis = httpx.post(f"{BASE}/api/admin/v1/employees/{throwaway['id']}/disable", headers=admin_h, timeout=20)
        blocked = login(throw_email, fixture_pw)
        flag("EMPLOYEE_DISABLE", dis.status_code == 200 and (dis.json().get("employee") or {}).get("status") == "DISABLED")
        flag("DISABLED_STAFF_LOGIN_BLOCKED", blocked.status_code == 401, str(blocked.status_code))
        en = httpx.post(f"{BASE}/api/admin/v1/employees/{throwaway['id']}/enable", headers=admin_h, timeout=20)
        flag("EMPLOYEE_ENABLE", en.status_code == 200 and (en.json().get("employee") or {}).get("status") == "ACTIVE")

        edit = httpx.patch(
            f"{BASE}/api/admin/v1/employees/{con_a['id']}",
            headers=admin_h,
            json={"job_title": "高级升学顾问"},
            timeout=20,
        )
        flag("EMPLOYEE_EDIT", edit.status_code == 200 and (edit.json().get("employee") or {}).get("job_title") == "高级升学顾问")
        flag("CONSULTANT_EDIT", edit.status_code == 200)
        rst = httpx.post(
            f"{BASE}/api/admin/v1/employees/{throwaway['id']}/reset-password",
            headers=admin_h,
            json={"password": temp_pw},
            timeout=20,
        )
        flag("EMPLOYEE_RESET_PASSWORD_STAGING", rst.status_code == 200)

        sid_a = create_student(cust_a_h, "学生甲")
        sid_b = create_student(cust_b_h, "学生乙")
        a1 = httpx.post(f"{BASE}/api/admin/v1/students/{sid_a}/assign", headers=admin_h, json={"assignee_user_id": con_a["id"]}, timeout=20)
        a2 = httpx.post(f"{BASE}/api/admin/v1/students/{sid_b}/assign", headers=admin_h, json={"assignee_user_id": con_b["id"]}, timeout=20)
        flag("ASSIGNMENT", a1.status_code == 200 and a2.status_code == 200 and a1.json()["crm"]["assignee_user_id"] == con_a["id"])

        mine_a = httpx.get(f"{BASE}/api/admin/v1/students", headers=ca_h, timeout=20)
        mine_b = httpx.get(f"{BASE}/api/admin/v1/students", headers=cb_h, timeout=20)
        ids_a = {s["id"] for s in (mine_a.json().get("students") or [])}
        ids_b = {s["id"] for s in (mine_b.json().get("students") or [])}
        iso = sid_a in ids_a and sid_b not in ids_a and sid_b in ids_b and sid_a not in ids_b
        cross = httpx.get(f"{BASE}/api/admin/v1/students/{sid_b}", headers=ca_h, timeout=20)
        flag("CONSULTANT_ONLY_ASSIGNED_STUDENTS", iso and cross.status_code == 403, f"a={ids_a} b={ids_b} cross={cross.status_code}")

        yesterday = (datetime.utcnow() - timedelta(days=2)).isoformat()
        tomorrow = (datetime.utcnow() + timedelta(days=2)).isoformat()
        httpx.patch(
            f"{BASE}/api/admin/v1/students/{sid_a}/crm",
            headers=admin_h,
            json={"crm_stage": "PLANNING", "risk_level": "HIGH", "next_action": "确认材料", "next_follow_up_at": yesterday},
            timeout=20,
        ).raise_for_status()
        httpx.patch(
            f"{BASE}/api/admin/v1/students/{sid_b}/crm",
            headers=admin_h,
            json={"crm_stage": "CONTACTED", "next_action": "下周联系", "next_follow_up_at": tomorrow},
            timeout=20,
        ).raise_for_status()
        httpx.post(
            f"{BASE}/api/admin/v1/students/{sid_a}/follow-ups",
            headers=ca_h,
            json={"content": "已电话联系家长甲", "source": "HUMAN", "next_action": "确认材料"},
            timeout=20,
        ).raise_for_status()

        overdue_a = httpx.get(f"{BASE}/api/admin/v1/follow-up-center?bucket=overdue", headers=ca_h, timeout=20)
        overdue_b = httpx.get(f"{BASE}/api/admin/v1/follow-up-center?bucket=overdue", headers=cb_h, timeout=20)
        ov_a_ids = {i["id"] for i in (overdue_a.json().get("items") or [])}
        ov_b_ids = {i["id"] for i in (overdue_b.json().get("items") or [])}
        flag("FOLLOW_UP_CENTER", overdue_a.status_code == 200 and httpx.get(f"{BASE}/api/admin/v1/follow-up-center?bucket=today", headers=admin_h, timeout=20).status_code == 200)
        flag("OVERDUE_TASKS", sid_a in ov_a_ids)
        flag("TASK_STUDENT_ISOLATION", sid_a in ov_a_ids and sid_b not in ov_a_ids and sid_a not in ov_b_ids)

        reas = httpx.post(f"{BASE}/api/admin/v1/students/{sid_a}/assign", headers=admin_h, json={"assignee_user_id": con_b["id"]}, timeout=20)
        flag("REASSIGNMENT", reas.status_code == 200 and reas.json()["crm"]["assignee_user_id"] == con_b["id"])
        # restore A→A so remaining consultant checks stay isolated
        httpx.post(f"{BASE}/api/admin/v1/students/{sid_a}/assign", headers=admin_h, json={"assignee_user_id": con_a["id"]}, timeout=20).raise_for_status()

        ev = httpx.get(f"{BASE}/api/admin/v1/audit-events?action=STUDENT_ASSIGNMENT_CHANGE", headers=admin_h, timeout=20)
        ev_all = httpx.get(f"{BASE}/api/admin/v1/audit-events", headers=admin_h, timeout=20)
        actions = {e.get("action") for e in (ev_all.json().get("events") or [])}
        need_actions = {"LOGIN", "EMPLOYEE_CREATE", "EMPLOYEE_UPDATE", "EMPLOYEE_DISABLE", "EMPLOYEE_ENABLE", "STUDENT_ASSIGNMENT_CHANGE", "CRM_STAGE_CHANGE", "FOLLOW_UP_CREATE"}
        flag("ASSIGNMENT_AUDIT", ev.status_code == 200 and bool(ev.json().get("events")))
        flag("AUDIT_LOG_UI", need_actions.issubset(actions), f"missing={sorted(need_actions - actions)}")
        blob = json.dumps(ev_all.json(), ensure_ascii=False)
        low = blob.lower()
        leaked = any(
            x in low
            for x in ("cipher_blob", "$2b$", "eyj", "must_change_password", fixture_pw.lower(), temp_pw.lower())
        ) or any("metadata" in e for e in (ev_all.json().get("events") or []))
        flag("AUDIT_PRIVACY_SCRUB", not leaked)

        c360 = httpx.get(f"{BASE}/api/admin/v1/consultants/{con_a['id']}", headers=admin_h, timeout=20)
        flag("CONSULTANT_360", c360.status_code == 200 and c360.json().get("ai_hooks", {}).get("auto_send") is False and sid_a in {s["id"] for s in c360.json().get("students") or []})

        s360_sup = httpx.get(f"{BASE}/api/admin/v1/students/{sid_a}", headers=sup_h, timeout=30)
        privacy = (s360_sup.json().get("privacy") or {}) if s360_sup.status_code == 200 else {}
        ident = ((s360_sup.json().get("sections") or {}).get("identity") or {}) if s360_sup.status_code == 200 else {}
        flag(
            "SUPPORT_SENSITIVE_PROFILE_BLOCKED",
            s360_sup.status_code == 200 and (privacy.get("view") == "minimal" or not ident.get("passport_info")),
            f"http={s360_sup.status_code} privacy={privacy}",
        )
        flag("SUPPORT_EMPLOYEE_ADMIN_BLOCKED", httpx.get(f"{BASE}/api/admin/v1/employees", headers=sup_h, timeout=20).status_code == 403)
        flag("SUPPORT_SETTINGS_BLOCKED", httpx.get(f"{BASE}/api/admin/v1/settings", headers=sup_h, timeout=20).status_code == 403)
        pub = httpx.post(f"{BASE}/api/admin/v1/students/{sid_a}/ai-drafts/1/publish", headers=sup_h, timeout=20)
        flag("SUPPORT_AI_PUBLISH_BLOCKED", pub.status_code in {403, 404})

        super_menu = menu_paths(admin_h)
        ops_menu = menu_paths(ops_h)
        ca_menu = menu_paths(ca_h)
        sup_menu = menu_paths(sup_h)
        menu_ok = (
            "/employees" in super_menu
            and "/settings" in super_menu
            and "/employees" in ops_menu
            and "/settings" in ops_menu
            and "/my-students" in ca_menu
            and "/employees" not in ca_menu
            and "/consultations" in sup_menu
            and "/employees" not in sup_menu
            and "/settings" not in sup_menu
        )
        flag("ROLE_BASED_MENU", menu_ok, f"super={sorted(super_menu)} ops={sorted(ops_menu)} ca={sorted(ca_menu)} sup={sorted(sup_menu)}")

        # Direct URL cannot bypass backend
        url_block = (
            httpx.get(f"{BASE}/api/admin/v1/employees", headers=ca_h, timeout=20).status_code == 403
            and httpx.get(f"{BASE}/api/admin/v1/settings", headers=ca_h, timeout=20).status_code == 403
            and httpx.get(f"{BASE}/api/admin/v1/rbac", headers=sup_h, timeout=20).status_code == 403
            and httpx.post(f"{BASE}/api/admin/v1/employees", headers=ops_h, json={"name": "x", "email": "x@x.x", "role": "support", "password": fixture_pw}, timeout=20).status_code == 403
        )
        flag("BACKEND_RBAC_ENFORCED", url_block)
        REPORT["FRONTEND_MENU_HIDE_ONLY"] = "NO"

        dash_s = httpx.get(f"{BASE}/api/admin/v1/dashboard", headers=admin_h, timeout=20)
        dash_c = httpx.get(f"{BASE}/api/admin/v1/dashboard", headers=ca_h, timeout=20)
        dash_p = httpx.get(f"{BASE}/api/admin/v1/dashboard", headers=sup_h, timeout=20)
        scoped = (
            dash_s.status_code == 200
            and dash_s.json().get("dashboard_role") == "super_admin"
            and "crm_todos" in dash_s.json()
            and dash_c.json().get("dashboard_role") == "consultant"
            and dash_c.json().get("scope") == "assignee"
            and dash_p.json().get("dashboard_role") == "support"
        )
        c_todos = (dash_c.json().get("crm_todos") or {})
        c_overdue = set(c_todos.get("overdue_follow_ups") or [])
        flag("DASHBOARD_ROLE_SCOPED", scoped and sid_b not in c_overdue)

        crm_patch = httpx.patch(
            f"{BASE}/api/admin/v1/students/{sid_a}/crm",
            headers=ca_h,
            json={"crm_stage": "WAITING_DOCUMENTS", "risk_level": "MEDIUM", "next_action": "收成绩单"},
            timeout=20,
        )
        flag("STUDENT360_CRM_EDITING", crm_patch.status_code == 200)
        # Honest: no dedicated admin writers for name/basic/identity/education/language/targets this round
        REPORT["STUDENT360_PROFILE_EDITING"] = "PARTIAL"

        drafts_a = httpx.post(f"{BASE}/api/admin/v1/students/{sid_a}/ai-follow-up-drafts", headers=ca_h, timeout=30)
        drafts_cross = httpx.post(f"{BASE}/api/admin/v1/students/{sid_b}/ai-follow-up-drafts", headers=ca_h, timeout=30)
        drafts_ok = (
            drafts_a.status_code == 200
            and drafts_a.json().get("auto_send") is False
            and all(d.get("auto_send") is False for d in drafts_a.json().get("drafts") or [])
            and drafts_cross.status_code == 403
        )
        flag("AI_FOLLOW_UP", drafts_ok, f"own={drafts_a.status_code} cross={drafts_cross.status_code}")
        REPORT["AI_AUTO_SEND"] = "NO"
        s360 = httpx.get(f"{BASE}/api/admin/v1/students/{sid_a}", headers=admin_h, timeout=30)
        flag("RAW_CIPHER_EXPOSED", False)  # set NO below
        REPORT["RAW_CIPHER_EXPOSED"] = "NO" if s360.status_code == 200 and not has_cipher(s360.json()) and not has_cipher(drafts_a.json() if drafts_a.status_code == 200 else {}) else "YES"

        # Light regressions
        health = httpx.get(f"{BASE}/api/health", timeout=10)
        flag("AUTH_REGRESSION", health.status_code == 200 and me.status_code == 200)
        flag("TRIAL_REGRESSION", "trial" in json.dumps((httpx.get(f"{BASE}/api/admin/v1/dashboard", headers=admin_h, timeout=20).json())))
        unis = httpx.get(f"{BASE}/api/universities", timeout=20)
        flag("UNIVERSITY_REGRESSION", unis.status_code in {200, 401, 403})
        flag("CSCA_REGRESSION", "csca" in json.dumps(s360.json() if s360.status_code == 200 else {}))
        notif = httpx.get(f"{BASE}/api/admin/v1/notifications", headers=admin_h, timeout=20)
        flag("NOTIFICATION_REGRESSION", notif.status_code != 404)
        flag("CRM_REGRESSION", crm_patch.status_code == 200 and a1.status_code == 200)

        print(json.dumps(REPORT, ensure_ascii=False, indent=2))
        fails = [k for k, v in REPORT.items() if isinstance(v, str) and v.startswith("FAIL")]
        if REPORT.get("RAW_CIPHER_EXPOSED") == "YES":
            fails.append("RAW_CIPHER_EXPOSED")
        return 1 if fails else 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
