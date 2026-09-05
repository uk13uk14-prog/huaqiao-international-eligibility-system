"""Staff / employee / consultant operations for Admin Console V2.

Never treat CUSTOMER / student-owner accounts as employees.
Never physically delete staff with history.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from ..models import AuthToken, StudentFollowUp, StudentMasterProfile, Tenant, User
from . import admin_audit
from .admin_rbac import (
    ASSIGNABLE_DB_ROLES,
    JOB_TITLE_PRESETS,
    ROLE_LABEL_ZH,
    STAFF_DB_ROLES,
    capabilities_for,
    is_customer_account,
    is_staff_account,
    resolve_console_role,
)
from .security import hash_password
from .student_crm import CRM_STAGES, staff_label, stage_label

EMPLOYEE_CREATE = "EMPLOYEE_CREATE"
EMPLOYEE_EDIT = "EMPLOYEE_EDIT"
EMPLOYEE_DISABLE = "EMPLOYEE_DISABLE"
EMPLOYEE_ENABLE = "EMPLOYEE_ENABLE"
EMPLOYEE_PASSWORD_RESET = "EMPLOYEE_PASSWORD_RESET"
STAFF_LOGIN = "STAFF_LOGIN"
STUDENT_ASSIGNMENT_CHANGE = "STUDENT_ASSIGNMENT_CHANGE"

WRITABLE_STAFF_ROLES = frozenset(
    {"super_admin", "operations_admin", "consultant", "support"}
)


def staff_status(user: User) -> str:
    return "ACTIVE" if user.is_active else "DISABLED"


def serialize_employee(db: Session, user: User) -> dict[str, Any]:
    assigned = (
        db.query(StudentMasterProfile)
        .filter(
            StudentMasterProfile.assignee_user_id == user.id,
            StudentMasterProfile.status != "DELETED",
        )
        .count()
    )
    console = resolve_console_role(user)
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name or "",
        "role": (console.value if console else (user.role or "")),
        "role_label": ROLE_LABEL_ZH.get(
            (console.value if console else user.role or ""), user.role or ""
        ),
        "job_title": getattr(user, "job_title", None) or "",
        "status": staff_status(user),
        "status_label": "正常" if user.is_active else "已停用",
        "account_kind": getattr(user, "account_kind", None) or "STAFF",
        "assigned_student_count": assigned,
        "last_login_at": user.last_login_at.isoformat() if getattr(user, "last_login_at", None) else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "must_change_password": bool(getattr(user, "must_change_password", False)),
        "is_active": bool(user.is_active),
    }


def list_employees(db: Session, *, role: str | None = None, q: str | None = None) -> list[dict]:
    rows = db.query(User).filter(User.role.in_(list(STAFF_DB_ROLES))).order_by(User.id.asc()).all()
    out = []
    for u in rows:
        if role and (u.role or "").lower() not in {role.lower(), "admin" if role == "super_admin" else role}:
            if role == "super_admin" and (u.role or "").lower() in {"admin", "super_admin"}:
                pass
            elif (u.role or "").lower() != role.lower():
                continue
        if q:
            ql = q.lower()
            blob = f"{u.email}{u.name}{u.id}{getattr(u, 'job_title', '')}".lower()
            if ql not in blob:
                continue
        out.append(serialize_employee(db, u))
    return out


def list_consultants(db: Session) -> list[dict]:
    rows = (
        db.query(User)
        .filter(User.role == "consultant")
        .order_by(User.id.asc())
        .all()
    )
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    out = []
    for u in rows:
        base = serialize_employee(db, u)
        assigned_q = db.query(StudentMasterProfile).filter(
            StudentMasterProfile.assignee_user_id == u.id,
            StudentMasterProfile.status != "DELETED",
        )
        due = assigned_q.filter(
            StudentMasterProfile.next_follow_up_at.isnot(None),
            StudentMasterProfile.next_follow_up_at >= start,
            StudentMasterProfile.next_follow_up_at < start.replace(hour=23, minute=59, second=59),
        ).count()
        overdue = assigned_q.filter(
            StudentMasterProfile.next_follow_up_at.isnot(None),
            StudentMasterProfile.next_follow_up_at < start,
        ).count()
        last_fu = (
            db.query(StudentFollowUp)
            .filter(StudentFollowUp.operator_user_id == u.id)
            .order_by(StudentFollowUp.created_at.desc())
            .first()
        )
        base.update(
            {
                "due_today_count": due,
                "overdue_count": overdue,
                "last_activity_at": last_fu.created_at.isoformat() if last_fu and last_fu.created_at else base["last_login_at"],
            }
        )
        out.append(base)
    return out


def consultant_360(db: Session, user: User) -> dict[str, Any]:
    if (user.role or "").lower() != "consultant":
        raise ValueError("not a consultant")
    header = serialize_employee(db, user)
    students = (
        db.query(StudentMasterProfile)
        .filter(
            StudentMasterProfile.assignee_user_id == user.id,
            StudentMasterProfile.status != "DELETED",
        )
        .order_by(StudentMasterProfile.updated_at.desc())
        .all()
    )
    stage_dist: dict[str, int] = {}
    for s in students:
        key = s.crm_stage or "UNASSIGNED"
        stage_dist[key] = stage_dist.get(key, 0) + 1
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today = [s for s in students if s.next_follow_up_at and s.next_follow_up_at >= start and s.next_follow_up_at < start.replace(hour=23, minute=59, second=59)]
    overdue = [s for s in students if s.next_follow_up_at and s.next_follow_up_at < start]
    follows = (
        db.query(StudentFollowUp)
        .filter(StudentFollowUp.operator_user_id == user.id)
        .order_by(StudentFollowUp.created_at.desc())
        .limit(20)
        .all()
    )
    return {
        "consultant": header,
        "students": [
            {
                "id": s.id,
                "display_name": s.display_name or "待补姓名",
                "crm_stage": s.crm_stage,
                "crm_stage_label": stage_label(s.crm_stage),
                "risk_level": s.risk_level or "NONE",
                "next_action": s.next_action or "",
                "next_follow_up_at": s.next_follow_up_at.isoformat() if s.next_follow_up_at else None,
            }
            for s in students
        ],
        "stage_distribution": [
            {"stage": k, "label": stage_label(k), "count": v} for k, v in stage_dist.items()
        ],
        "today_todos": [{"id": s.id, "display_name": s.display_name or "待补姓名", "next_action": s.next_action or ""} for s in today],
        "overdue": [{"id": s.id, "display_name": s.display_name or "待补姓名", "next_follow_up_at": s.next_follow_up_at.isoformat() if s.next_follow_up_at else None} for s in overdue],
        "recent_follow_ups": [
            {
                "id": f.id,
                "student_id": f.student_id,
                "summary": f.summary or f.content or "",
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in follows
        ],
        "workload": {
            "assigned": len(students),
            "today": len(today),
            "overdue": len(overdue),
        },
        "ai_hooks": {
            "consultant_summary": "RESERVED",
            "missed_follow_up": "RESERVED",
            "student_risk": "RESERVED",
            "auto_send": False,
        },
    }


def _platform_tenant_id(db: Session, operator: User) -> int:
    if operator.tenant_id:
        return operator.tenant_id
    t = db.query(Tenant).order_by(Tenant.id.asc()).first()
    if not t:
        t = Tenant(name="平台", tenant_type="platform")
        db.add(t)
        db.flush()
    return t.id


def create_employee(
    db: Session,
    *,
    operator: User,
    email: str,
    name: str,
    role: str,
    password: str,
    job_title: str = "",
    active: bool = True,
) -> User:
    email = (email or "").strip().lower()
    role = (role or "").strip().lower()
    if role == "admin":
        role = "super_admin"
    if role not in WRITABLE_STAFF_ROLES:
        raise ValueError("invalid staff role")
    if not email or "@" not in email:
        raise ValueError("invalid email")
    if not name.strip():
        raise ValueError("name required")
    if len(password or "") < 8:
        raise ValueError("password too short")
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        if is_customer_account(existing) and (existing.role or "").lower() not in STAFF_DB_ROLES:
            raise ValueError("email belongs to a customer/student-owner account")
        raise ValueError("email already exists")
    user = User(
        tenant_id=_platform_tenant_id(db, operator),
        email=email,
        name=name.strip(),
        password_hash=hash_password(password),
        role=role,
        plan_code="staff",
        is_active=bool(active),
        account_kind="STAFF",
        job_title=(job_title or "").strip(),
        must_change_password=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    admin_audit.record_audit(
        db,
        actor_user_id=operator.id,
        action=EMPLOYEE_CREATE,
        resource_type="user",
        resource_id=user.id,
        metadata={"email": email, "role": role, "job_title": user.job_title},
    )
    return user


def update_employee(
    db: Session,
    *,
    operator: User,
    user: User,
    name: str | None = None,
    role: str | None = None,
    job_title: str | None = None,
) -> User:
    if not is_staff_account(user):
        raise ValueError("not a staff account")
    if name is not None:
        user.name = name.strip()
    if job_title is not None:
        user.job_title = job_title.strip()
    if role is not None:
        role = role.strip().lower()
        if role == "admin":
            role = "super_admin"
        if role not in WRITABLE_STAFF_ROLES:
            raise ValueError("invalid staff role")
        # Never demote the last super admin implicitly — caller should check
        user.role = role
    db.add(user)
    db.commit()
    db.refresh(user)
    admin_audit.record_audit(
        db,
        actor_user_id=operator.id,
        action=EMPLOYEE_EDIT,
        resource_type="user",
        resource_id=user.id,
        metadata={"role": user.role, "job_title": user.job_title},
    )
    admin_audit.record_audit(
        db,
        actor_user_id=operator.id,
        action="EMPLOYEE_UPDATE",
        resource_type="user",
        resource_id=user.id,
        metadata={"role": user.role, "job_title": user.job_title},
    )
    return user


def set_employee_active(db: Session, *, operator: User, user: User, active: bool) -> User:
    if not is_staff_account(user):
        raise ValueError("not a staff account")
    if user.id == operator.id and not active:
        raise ValueError("cannot disable self")
    user.is_active = bool(active)
    db.add(user)
    if not active:
        db.query(AuthToken).filter(AuthToken.user_id == user.id).delete()
    db.commit()
    db.refresh(user)
    admin_audit.record_audit(
        db,
        actor_user_id=operator.id,
        action=EMPLOYEE_ENABLE if active else EMPLOYEE_DISABLE,
        resource_type="user",
        resource_id=user.id,
        metadata={"status": staff_status(user)},
    )
    return user


def reset_employee_password(db: Session, *, operator: User, user: User, password: str) -> None:
    if not is_staff_account(user):
        raise ValueError("not a staff account")
    if len(password or "") < 8:
        raise ValueError("password too short")
    user.password_hash = hash_password(password)
    user.must_change_password = True
    db.add(user)
    db.query(AuthToken).filter(AuthToken.user_id == user.id).delete()
    db.commit()
    admin_audit.record_audit(
        db,
        actor_user_id=operator.id,
        action=EMPLOYEE_PASSWORD_RESET,
        resource_type="user",
        resource_id=user.id,
        metadata={"must_change_password": True},
    )


def change_own_password(db: Session, *, user: User, new_password: str) -> None:
    if len(new_password or "") < 8:
        raise ValueError("password too short")
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    db.add(user)
    db.commit()


def mark_login(db: Session, user: User) -> None:
    user.last_login_at = datetime.utcnow()
    db.add(user)
    db.commit()
    if is_staff_account(user):
        admin_audit.record_audit(
            db,
            actor_user_id=user.id,
            action=STAFF_LOGIN,
            resource_type="user",
            resource_id=user.id,
            metadata={"role": user.role},
        )
        admin_audit.record_audit(
            db,
            actor_user_id=user.id,
            action="LOGIN",
            resource_type="user",
            resource_id=user.id,
            metadata={"role": user.role},
        )


def assignable_staff(db: Session) -> list[dict]:
    rows = (
        db.query(User)
        .filter(User.role.in_(list(ASSIGNABLE_DB_ROLES)))
        .filter(User.is_active.is_(True))
        .order_by(User.id.asc())
        .all()
    )
    return [
        {
            "id": u.id,
            "email": u.email,
            "name": u.name or "",
            "role": u.role,
            "role_label": ROLE_LABEL_ZH.get(u.role if u.role != "admin" else "super_admin", u.role),
            "job_title": getattr(u, "job_title", None) or "",
            "label": staff_label(u),
            "status": "ACTIVE",
        }
        for u in rows
    ]


def follow_up_center(db: Session, *, assignee_user_id: int | None, bucket: str) -> list[dict]:
    now = datetime.utcnow()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    q = db.query(StudentMasterProfile).filter(StudentMasterProfile.status != "DELETED")
    if assignee_user_id:
        q = q.filter(StudentMasterProfile.assignee_user_id == assignee_user_id)
    if bucket == "today":
        q = q.filter(
            StudentMasterProfile.next_follow_up_at.isnot(None),
            StudentMasterProfile.next_follow_up_at >= start,
            StudentMasterProfile.next_follow_up_at < start.replace(hour=23, minute=59, second=59),
        )
    elif bucket == "upcoming":
        q = q.filter(
            StudentMasterProfile.next_follow_up_at.isnot(None),
            StudentMasterProfile.next_follow_up_at >= start.replace(hour=23, minute=59, second=59),
        )
    elif bucket == "overdue":
        q = q.filter(
            StudentMasterProfile.next_follow_up_at.isnot(None),
            StudentMasterProfile.next_follow_up_at < start,
        )
    elif bucket == "done":
        q = q.filter(StudentMasterProfile.crm_stage.in_(["COMPLETED", "PAUSED"]))
    else:
        q = q.filter(StudentMasterProfile.next_follow_up_at.isnot(None))
    rows = q.order_by(StudentMasterProfile.next_follow_up_at.asc()).limit(200).all()
    return [
        {
            "id": s.id,
            "display_name": s.display_name or "待补姓名",
            "crm_stage": s.crm_stage,
            "crm_stage_label": stage_label(s.crm_stage),
            "risk_level": s.risk_level or "NONE",
            "next_action": s.next_action or "",
            "next_follow_up_at": s.next_follow_up_at.isoformat() if s.next_follow_up_at else None,
            "assignee_user_id": s.assignee_user_id,
        }
        for s in rows
    ]


def role_catalog() -> dict:
    from .admin_rbac import ROLE_CAPABILITIES, AdminConsoleRole

    return {
        "roles": [
            {
                "key": r.value,
                "label": ROLE_LABEL_ZH[r.value],
                "capabilities": sorted(ROLE_CAPABILITIES[r]),
            }
            for r in AdminConsoleRole
        ],
        "job_titles": list(JOB_TITLE_PRESETS),
        "stages": list(CRM_STAGES),
    }
