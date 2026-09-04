"""Admin Console API V1 — /api/admin/v1/*

Read-focused Student 360 + AI Expert draft workspace.
Never returns cipher_blob. Eligibility mapping is conservative (no cross-leak).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .database import get_db
from .models import (
    EligibilityRecord,
    ExpertConsultation,
    StudentMasterProfile,
    StudentTimelineItem,
    User,
)
from .services.admin_ai_expert import (
    REPORT_KINDS,
    approve_draft,
    generate_draft,
    list_drafts,
    provider_status,
    publish_draft,
    update_draft,
)
from .services.admin_privacy import public_student_meta, redact_profile_for_admin
from .services.admin_rbac import (
    rbac_proposal,
    require_admin_console,
    require_capability,
    resolve_console_role,
)
from .services.membership_trial import is_trial_plan, trial_info
from .services.security import is_paid
from .services.student_profile import empty_profile, normalize_profile, profile_summary
from .services.student_timeline import serialize_item
from .services.vault_crypto import decrypt_profile_json

router = APIRouter(prefix="/api/admin/v1", tags=["admin-v1"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decrypt_student_profile(row: StudentMasterProfile) -> dict:
    if not row.cipher_blob:
        return empty_profile()
    try:
        return normalize_profile(decrypt_profile_json(row.cipher_blob))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="学生档案解密失败") from exc


def _user_brief(u: User | None) -> dict | None:
    if not u:
        return None
    t = trial_info(u)
    return {
        "id": u.id,
        "email": u.email,
        "name": u.name or "",
        "role": u.role,
        "plan_code": u.plan_code,
        "membership_until": u.membership_until.isoformat() if u.membership_until else None,
        "is_paid": is_paid(u),
        "trial": t,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "is_active": u.is_active,
        "tenant_id": u.tenant_id,
    }


def _get_student_or_404(db: Session, student_id: int) -> StudentMasterProfile:
    row = db.query(StudentMasterProfile).filter(StudentMasterProfile.id == student_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="学生不存在")
    return row


def _console_role_str(admin: User) -> str:
    r = resolve_console_role(admin)
    return r.value if r else "unknown"


def _map_legacy_eligibility(db: Session, student: StudentMasterProfile) -> dict:
    """eligibility_records are user-scoped — never guess across multi-student accounts."""
    siblings = (
        db.query(StudentMasterProfile)
        .filter(
            StudentMasterProfile.user_id == student.user_id,
            StudentMasterProfile.status != "DELETED",
        )
        .all()
    )
    sibling_count = len(siblings)
    records = (
        db.query(EligibilityRecord)
        .filter(EligibilityRecord.user_id == student.user_id)
        .order_by(EligibilityRecord.created_at.desc())
        .limit(50)
        .all()
    )

    def _ser(r: EligibilityRecord) -> dict:
        raw = r.raw_input or "{}"
        try:
            raw_obj = json.loads(raw) if isinstance(raw, str) else {}
        except json.JSONDecodeError:
            raw_obj = {}
        # Mask passport-like fields in raw_input
        from .services.privacy import mask_sensitive_fields

        raw_masked = mask_sensitive_fields(raw_obj) if isinstance(raw_obj, dict) else {}
        return {
            "id": r.id,
            "eligibility_type": r.eligibility_type,
            "qualified": r.qualified,
            "conclusion": r.conclusion,
            "reasons": r.reasons,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "raw_input_masked": raw_masked,
            "mapping_status": "LEGACY_USER_SCOPED",
            "student_id": None,
        }

    if sibling_count > 1:
        return {
            "mapping_status": "UNRESOLVED",
            "message": "历史资格记录尚未绑定到具体学生",
            "reason": "owner_has_multiple_students",
            "student_count_for_owner": sibling_count,
            "legacy_record_count": len(records),
            "international": None,
            "huaqiao": None,
            "records": [],
        }

    if sibling_count == 1 and records:
        items = [_ser(r) for r in records]
        intl = next((x for x in items if x["eligibility_type"] == "international"), None)
        hq = next((x for x in items if x["eligibility_type"] in ("huaqiao", "overseas_chinese")), None)
        return {
            "mapping_status": "LEGACY_USER_SCOPED",
            "message": "资格记录按 user_id 关联；当前用户仅有一名学生，只读回退展示。",
            "student_count_for_owner": 1,
            "legacy_record_count": len(records),
            "international": intl,
            "huaqiao": hq,
            "records": items,
        }

    return {
        "mapping_status": "EMPTY",
        "message": "无历史资格记录",
        "student_count_for_owner": sibling_count,
        "legacy_record_count": 0,
        "international": None,
        "huaqiao": None,
        "records": [],
    }


def _map_legacy_consultations(db: Session, student: StudentMasterProfile) -> dict:
    siblings = (
        db.query(StudentMasterProfile)
        .filter(
            StudentMasterProfile.user_id == student.user_id,
            StudentMasterProfile.status != "DELETED",
        )
        .count()
    )
    mem = list_drafts(student.id)
    if siblings > 1:
        return {
            "mapping_status": "UNRESOLVED",
            "message": "历史一对一咨询按 user_id 存储，多学生时禁止归属猜测",
            "db_consultations": [],
            "ai_drafts": mem,
        }
    rows = (
        db.query(ExpertConsultation)
        .filter(ExpertConsultation.user_id == student.user_id)
        .order_by(ExpertConsultation.created_at.desc())
        .limit(50)
        .all()
    )
    return {
        "mapping_status": "LEGACY_USER_SCOPED" if rows else "EMPTY",
        "db_consultations": [
            {
                "id": r.id,
                "title": r.title,
                "status": r.status,
                "student_id": None,
                "mapping_status": "LEGACY_USER_SCOPED",
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "published_at": r.published_at.isoformat() if r.published_at else None,
            }
            for r in rows
        ],
        "ai_drafts": mem,
    }


# ---------------------------------------------------------------------------
# Auth / meta
# ---------------------------------------------------------------------------

@router.get("/me")
def admin_me(admin: User = Depends(require_admin_console)):
    console = resolve_console_role(admin)
    return {
        "user": _user_brief(admin),
        "console_role": console.value if console else None,
        "rbac": rbac_proposal(),
        "ai_provider": provider_status(),
    }


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("/dashboard")
def dashboard(admin: User = Depends(require_capability("admin.dashboard")), db: Session = Depends(get_db)):
    now = datetime.utcnow()
    users = db.query(User).all()
    total_users = len(users)
    trial_users = 0
    paid_users = 0
    trial_expiring_soon = 0
    for u in users:
        t = trial_info(u)
        if t.get("trial_active"):
            trial_users += 1
            until = u.membership_until
            if until and until <= now + timedelta(days=2):
                trial_expiring_soon += 1
        elif is_paid(u) and not is_trial_plan(u.plan_code):
            paid_users += 1

    student_count = db.query(StudentMasterProfile).filter(StudentMasterProfile.status != "DELETED").count()
    pending_review = (
        db.query(ExpertConsultation)
        .filter(ExpertConsultation.status.in_(["draft_ready", "pending_ai", "pending_review"]))
        .count()
    )
    recent = (
        db.query(ExpertConsultation)
        .order_by(ExpertConsultation.created_at.desc())
        .limit(10)
        .all()
    )
    return {
        "total_users": total_users,
        "trial_users": trial_users,
        "paid_users": paid_users,
        "trial_expiring_soon": trial_expiring_soon,
        "student_profiles": student_count,
        "pending_human_review": pending_review,
        "recent_consultations": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "title": r.title,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in recent
        ],
        "bi": "simple_v1",
    }


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@router.get("/users")
def list_users(
    q: str | None = Query(None),
    admin: User = Depends(require_capability("admin.users.read")),
    db: Session = Depends(get_db),
):
    rows = db.query(User).order_by(User.created_at.desc()).limit(500).all()
    out = []
    for u in rows:
        if q:
            ql = q.lower()
            if ql not in (u.email or "").lower() and ql not in (u.name or "").lower() and ql != str(u.id):
                continue
        sc = (
            db.query(StudentMasterProfile)
            .filter(StudentMasterProfile.user_id == u.id, StudentMasterProfile.status != "DELETED")
            .count()
        )
        brief = _user_brief(u)
        brief["student_count"] = sc
        out.append(brief)
    return {"users": out, "count": len(out)}


@router.get("/users/{user_id}")
def get_user(
    user_id: int,
    admin: User = Depends(require_capability("admin.users.read")),
    db: Session = Depends(get_db),
):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")
    students = (
        db.query(StudentMasterProfile)
        .filter(StudentMasterProfile.user_id == user_id, StudentMasterProfile.status != "DELETED")
        .order_by(StudentMasterProfile.updated_at.desc())
        .all()
    )
    brief = _user_brief(u)
    brief["student_count"] = len(students)
    return {
        "user": brief,
        "students": [public_student_meta(s) for s in students],
    }


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------

@router.get("/students")
def list_students(
    q: str | None = Query(None),
    admin: User = Depends(require_capability("admin.students.read")),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(StudentMasterProfile)
        .filter(StudentMasterProfile.status != "DELETED")
        .order_by(StudentMasterProfile.updated_at.desc())
        .limit(500)
        .all()
    )
    items = []
    for s in rows:
        owner = db.query(User).filter(User.id == s.user_id).first()
        meta = public_student_meta(s)
        meta["owner"] = {"id": owner.id, "email": owner.email, "name": owner.name} if owner else None
        # Goal hints without full decrypt leak: light decrypt for search/display only
        try:
            prof = _decrypt_student_profile(s)
            summary = profile_summary(prof)
            targets = summary.get("target_universities") or []
            meta["goal_hint"] = "、".join([t for t in targets if t][:3])
            meta["summary"] = {
                "chinese_name": summary.get("chinese_name") or "",
                "intended_entry_year": summary.get("intended_entry_year") or "",
            }
        except HTTPException:
            meta["goal_hint"] = ""
            meta["summary"] = {}
        if q:
            ql = q.lower()
            blob = f"{meta.get('display_name')}{meta.get('summary')}{owner.email if owner else ''}{s.id}".lower()
            if ql not in blob:
                continue
        items.append(meta)
    return {"students": items, "count": len(items)}


@router.get("/students/{student_id}")
def student_360(
    student_id: int,
    admin: User = Depends(require_capability("admin.student360.read")),
    db: Session = Depends(get_db),
):
    """Student 360 read-only V1 — strictly keyed by student_id."""
    row = _get_student_or_404(db, student_id)
    owner = db.query(User).filter(User.id == row.user_id).first()
    role = _console_role_str(admin)
    raw = _decrypt_student_profile(row)
    profile = redact_profile_for_admin(raw, role="support" if role == "support" else "consultant")

    # Never include cipher
    assert "cipher_blob" not in profile

    basic = profile.get("basic_info") or {}
    identity = profile.get("identity") or {}
    education = profile.get("education") or {}
    goals = profile.get("goals") or {}
    courses = profile.get("courses") or {}
    language = courses.get("language_exams") or []

    eligibility = _map_legacy_eligibility(db, row)
    consultations = _map_legacy_consultations(db, row)
    timeline_rows = (
        db.query(StudentTimelineItem)
        .filter(StudentTimelineItem.student_id == student_id)
        .all()
    )
    timeline_rows.sort(key=lambda r: ((r.deadline.isoformat() if r.deadline else "9999-12-31"), r.id or 0))
    # Extra isolation: timeline rows must match student_id (already filtered)
    for t in timeline_rows:
        if t.student_id != student_id:
            raise HTTPException(status_code=500, detail="timeline isolation violation")

    return {
        "student_id": student_id,
        "meta": public_student_meta(row),
        "owner": _user_brief(owner),
        "sections": {
            "basic_info": basic,
            "identity": identity,
            "education": education,
            "language_exams": language,
            "goals": goals,
            "planning": profile.get("planning") or {},
            "summary": profile.get("summary") or profile_summary(raw),
        },
        "eligibility": eligibility,
        "timeline": [serialize_item(t) for t in timeline_rows],
        "consultations": consultations,
        "consultant_notes": {
            "placeholder": True,
            "notes": [],
            "message": "顾问备注将在 Phase 3 持久化",
        },
        "privacy": profile.get("_privacy") or {"masked": True},
        "ai_provider": provider_status(),
    }


@router.get("/students/{student_id}/timeline")
def student_timeline(
    student_id: int,
    admin: User = Depends(require_capability("admin.student360.read")),
    db: Session = Depends(get_db),
):
    _get_student_or_404(db, student_id)
    rows = (
        db.query(StudentTimelineItem)
        .filter(StudentTimelineItem.student_id == student_id)
        .all()
    )
    rows.sort(key=lambda r: ((r.deadline.isoformat() if r.deadline else "9999-12-31"), r.id or 0))
    return {"student_id": student_id, "timeline": [serialize_item(t) for t in rows]}


@router.get("/students/{student_id}/eligibility")
def student_eligibility(
    student_id: int,
    admin: User = Depends(require_capability("admin.student360.read")),
    db: Session = Depends(get_db),
):
    row = _get_student_or_404(db, student_id)
    return {"student_id": student_id, **_map_legacy_eligibility(db, row)}


@router.get("/students/{student_id}/consultations")
def student_consultations(
    student_id: int,
    admin: User = Depends(require_capability("admin.student360.read")),
    db: Session = Depends(get_db),
):
    row = _get_student_or_404(db, student_id)
    return {"student_id": student_id, **_map_legacy_consultations(db, row)}


# ---------------------------------------------------------------------------
# AI Expert Workspace
# ---------------------------------------------------------------------------

class AiGenerateIn(BaseModel):
    report_kind: str = Field(..., description="One of REPORT_KINDS keys")


class AiEditIn(BaseModel):
    content: str


@router.get("/students/{student_id}/ai/report-kinds")
def ai_report_kinds(
    student_id: int,
    admin: User = Depends(require_capability("admin.ai.generate")),
    db: Session = Depends(get_db),
):
    _get_student_or_404(db, student_id)
    return {"student_id": student_id, "report_kinds": REPORT_KINDS, "ai_provider": provider_status()}


@router.get("/students/{student_id}/ai/drafts")
def ai_list_drafts(
    student_id: int,
    admin: User = Depends(require_capability("admin.ai.generate")),
    db: Session = Depends(get_db),
):
    _get_student_or_404(db, student_id)
    return {"student_id": student_id, "drafts": list_drafts(student_id)}


@router.post("/students/{student_id}/ai/generate")
async def ai_generate(
    student_id: int,
    body: AiGenerateIn,
    admin: User = Depends(require_capability("admin.ai.generate")),
    db: Session = Depends(get_db),
):
    row = _get_student_or_404(db, student_id)
    owner = db.query(User).filter(User.id == row.user_id).first()
    # Isolation: decrypt ONLY this student row
    profile = _decrypt_student_profile(row)
    # Cross-leak guard: ensure we did not load another student's id
    if row.id != student_id:
        raise HTTPException(status_code=500, detail="student_id isolation violation")

    try:
        draft = await generate_draft(
            student_id=student_id,
            report_kind=body.report_kind,
            profile=profile,
            actor_user_id=admin.id,
            owner={"id": owner.id, "email": owner.email} if owner else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    assert draft["status"] == "DRAFT"
    assert draft["published"] is False
    assert draft["auto_published"] is False
    return {"student_id": student_id, "draft": draft, "flow": "AI_GENERATE→DRAFT→EDIT→APPROVE→PUBLISH"}


@router.patch("/students/{student_id}/ai/drafts/{draft_id}")
def ai_edit_draft(
    student_id: int,
    draft_id: str,
    body: AiEditIn,
    admin: User = Depends(require_capability("admin.ai.edit")),
    db: Session = Depends(get_db),
):
    _get_student_or_404(db, student_id)
    updated = update_draft(student_id, draft_id, body.content, admin.id)
    if not updated:
        raise HTTPException(status_code=404, detail="草稿不存在")
    return {"student_id": student_id, "draft": updated}


@router.post("/students/{student_id}/ai/drafts/{draft_id}/approve")
def ai_approve(
    student_id: int,
    draft_id: str,
    admin: User = Depends(require_capability("admin.ai.approve")),
    db: Session = Depends(get_db),
):
    _get_student_or_404(db, student_id)
    updated = approve_draft(student_id, draft_id, admin.id)
    if not updated:
        raise HTTPException(status_code=404, detail="草稿不存在")
    assert updated["published"] is False
    return {"student_id": student_id, "draft": updated}


@router.post("/students/{student_id}/ai/drafts/{draft_id}/publish")
def ai_publish(
    student_id: int,
    draft_id: str,
    admin: User = Depends(require_capability("admin.ai.publish")),
    db: Session = Depends(get_db),
):
    _get_student_or_404(db, student_id)
    try:
        publish_draft(student_id, draft_id, admin.id)
    except KeyError:
        raise HTTPException(status_code=404, detail="草稿不存在") from None
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise HTTPException(status_code=409, detail="PUBLISH_BLOCKED")


@router.get("/settings")
def settings_view(admin: User = Depends(require_capability("admin.settings"))):
    return {
        "admin_domain": "https://admin.guoqiaoplan.com",
        "rbac": rbac_proposal(),
        "ai_provider": provider_status(),
        "migration_status": {
            "draft_file": "alembic/drafts/007_admin_ai_expert_v1_NOT_APPLIED.py",
            "applied": False,
            "production_db_changed": False,
        },
    }
