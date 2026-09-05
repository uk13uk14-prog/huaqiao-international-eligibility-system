"""Admin Console V2 endpoints — staff, RBAC catalog, audit, follow-up center."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .database import get_db
from .models import AuditEvent, User
from .services import admin_staff as staff
from .services.admin_rbac import (
    ROLE_LABEL_ZH,
    capabilities_for,
    consultant_scoped,
    menu_for,
    require_admin_console,
    require_capability,
    resolve_console_role,
    rbac_proposal,
)
from .services.security import hash_password  # noqa: F401  — used by reset via staff service

router = APIRouter(prefix="/api/admin/v1", tags=["admin-v2"])


class EmployeeCreateIn(BaseModel):
    name: str = Field(..., min_length=1)
    email: str = Field(..., min_length=3)
    role: str
    job_title: str = ""
    password: str = Field(..., min_length=8)
    status: str = "ACTIVE"


class EmployeePatchIn(BaseModel):
    name: str | None = None
    role: str | None = None
    job_title: str | None = None


class PasswordResetIn(BaseModel):
    password: str = Field(..., min_length=8)


class OwnPasswordIn(BaseModel):
    password: str = Field(..., min_length=8)


def _staff_or_404(db: Session, employee_id: int) -> User:
    u = db.query(User).filter(User.id == employee_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="员工不存在")
    return u


@router.get("/rbac")
def rbac_catalog(admin: User = Depends(require_capability("roles.read"))):
    return {**rbac_proposal(), **staff.role_catalog()}


@router.get("/employees")
def list_employees(
    q: str | None = Query(None),
    role: str | None = Query(None),
    admin: User = Depends(require_capability("employees.read")),
    db: Session = Depends(get_db),
):
    return {"employees": staff.list_employees(db, role=role, q=q)}


@router.post("/employees")
def create_employee(
    payload: EmployeeCreateIn,
    admin: User = Depends(require_capability("employees.write")),
    db: Session = Depends(get_db),
):
    try:
        user = staff.create_employee(
            db,
            operator=admin,
            email=payload.email,
            name=payload.name,
            role=payload.role,
            password=payload.password,
            job_title=payload.job_title,
            active=payload.status.upper() != "DISABLED",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"employee": staff.serialize_employee(db, user)}


@router.get("/employees/{employee_id}")
def get_employee(
    employee_id: int,
    admin: User = Depends(require_capability("employees.read")),
    db: Session = Depends(get_db),
):
    u = _staff_or_404(db, employee_id)
    return {"employee": staff.serialize_employee(db, u)}


@router.patch("/employees/{employee_id}")
def patch_employee(
    employee_id: int,
    payload: EmployeePatchIn,
    admin: User = Depends(require_capability("employees.write")),
    db: Session = Depends(get_db),
):
    u = _staff_or_404(db, employee_id)
    try:
        u = staff.update_employee(
            db,
            operator=admin,
            user=u,
            name=payload.name,
            role=payload.role,
            job_title=payload.job_title,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"employee": staff.serialize_employee(db, u)}


@router.post("/employees/{employee_id}/disable")
def disable_employee(
    employee_id: int,
    admin: User = Depends(require_capability("employees.write")),
    db: Session = Depends(get_db),
):
    u = _staff_or_404(db, employee_id)
    try:
        u = staff.set_employee_active(db, operator=admin, user=u, active=False)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"employee": staff.serialize_employee(db, u)}


@router.post("/employees/{employee_id}/enable")
def enable_employee(
    employee_id: int,
    admin: User = Depends(require_capability("employees.write")),
    db: Session = Depends(get_db),
):
    u = _staff_or_404(db, employee_id)
    try:
        u = staff.set_employee_active(db, operator=admin, user=u, active=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"employee": staff.serialize_employee(db, u)}


@router.post("/employees/{employee_id}/reset-password")
def reset_employee_password(
    employee_id: int,
    payload: PasswordResetIn,
    admin: User = Depends(require_capability("employees.write")),
    db: Session = Depends(get_db),
):
    u = _staff_or_404(db, employee_id)
    try:
        staff.reset_employee_password(db, operator=admin, user=u, password=payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "must_change_password": True}


@router.post("/me/password")
def change_own_password(
    payload: OwnPasswordIn,
    admin: User = Depends(require_admin_console),
    db: Session = Depends(get_db),
):
    try:
        staff.change_own_password(db, user=admin, new_password=payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True}


@router.get("/consultants")
def list_consultants(
    admin: User = Depends(require_capability("consultants.read")),
    db: Session = Depends(get_db),
):
    rows = staff.list_consultants(db)
    if consultant_scoped(admin):
        rows = [r for r in rows if r["id"] == admin.id]
    return {"consultants": rows}


@router.get("/consultants/{consultant_id}")
def get_consultant_360(
    consultant_id: int,
    admin: User = Depends(require_capability("consultants.read")),
    db: Session = Depends(get_db),
):
    if consultant_scoped(admin) and consultant_id != admin.id:
        raise HTTPException(status_code=403, detail="只能查看自己的顾问工作台")
    u = _staff_or_404(db, consultant_id)
    try:
        return staff.consultant_360(db, u)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/follow-up-center")
def follow_up_center(
    bucket: str = Query("today", description="today|upcoming|overdue|done"),
    admin: User = Depends(require_capability("followups.read")),
    db: Session = Depends(get_db),
):
    assignee = admin.id if consultant_scoped(admin) else None
    return {"bucket": bucket, "items": staff.follow_up_center(db, assignee_user_id=assignee, bucket=bucket)}


@router.get("/audit-events")
def list_audit_events(
    action: str | None = Query(None),
    admin: User = Depends(require_capability("audit.read")),
    db: Session = Depends(get_db),
):
    q = db.query(AuditEvent).order_by(AuditEvent.created_at.desc())
    if action:
        q = q.filter(AuditEvent.action == action)
    rows = q.limit(200).all()
    banned = ("password", "token", "cipher", "secret", "hash")
    items = []
    for r in rows:
        actor = db.query(User).filter(User.id == r.actor_user_id).first() if r.actor_user_id else None
        meta = r.metadata_json or "{}"
        low = meta.lower()
        if any(b in low for b in banned):
            meta = '{"redacted":true}'
        items.append(
            {
                "id": r.id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "actor_user_id": r.actor_user_id,
                "actor_label": (actor.name or actor.email) if actor else "系统",
                "action": r.action,
                "resource_type": r.resource_type,
                "resource_id": r.resource_id,
                "student_id": r.student_id,
                "summary": f"{r.action} · {r.resource_type} #{r.resource_id or '-'}",
                "result": "成功",
            }
        )
    return {"events": items}


@router.get("/nav")
def nav(admin: User = Depends(require_admin_console)):
    console = resolve_console_role(admin)
    return {
        "console_role": console.value if console else None,
        "role_label": ROLE_LABEL_ZH.get(console.value if console else "", ""),
        "permissions": capabilities_for(admin),
        "menu": menu_for(admin),
    }
