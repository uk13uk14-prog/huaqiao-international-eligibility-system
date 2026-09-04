"""Admin Console API V1 — frozen contract /api/admin/v1/*

Student 360 + AI Expert DRAFT→PUBLISH (student_id scoped).
Never returns cipher_blob.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

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
from .services import admin_ai_expert as ai
from .services import admin_audit
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

# Frozen contract path inventory (for docs/tests)
ADMIN_V1_CONTRACT = [
    "GET /api/admin/v1/dashboard",
    "GET /api/admin/v1/users",
    "GET /api/admin/v1/users/{user_id}",
    "GET /api/admin/v1/students",
    "GET /api/admin/v1/students/{student_id}",
    "GET /api/admin/v1/students/{student_id}/timeline",
    "GET /api/admin/v1/students/{student_id}/eligibility",
    "GET /api/admin/v1/students/{student_id}/consultations",
    "POST /api/admin/v1/students/{student_id}/ai-drafts",
    "GET /api/admin/v1/students/{student_id}/ai-drafts",
    "PATCH /api/admin/v1/students/{student_id}/ai-drafts/{draft_id}",
    "POST /api/admin/v1/students/{student_id}/ai-drafts/{draft_id}/approve",
    "POST /api/admin/v1/students/{student_id}/ai-drafts/{draft_id}/publish",
]


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


def _ser_eligibility(r: EligibilityRecord, mapping_status: str) -> dict:
    raw = r.raw_input or "{}"
    try:
        raw_obj = json.loads(raw) if isinstance(raw, str) else {}
    except json.JSONDecodeError:
        raw_obj = {}
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
        "mapping_status": mapping_status,
        "student_id": r.student_id,
    }


def _map_eligibility(db: Session, student: StudentMasterProfile) -> dict:
    """Prefer student_id-scoped rows; never guess legacy user-scoped across siblings."""
    scoped = (
        db.query(EligibilityRecord)
        .filter(EligibilityRecord.student_id == student.id)
        .order_by(EligibilityRecord.created_at.desc())
        .limit(50)
        .all()
    )
    if scoped:
        items = [_ser_eligibility(r, "STUDENT_SCOPED") for r in scoped]
        intl = next((x for x in items if x["eligibility_type"] == "international"), None)
        hq = next((x for x in items if x["eligibility_type"] in ("huaqiao", "overseas_chinese")), None)
        return {
            "mapping_status": "STUDENT_SCOPED",
            "message": "资格记录已绑定 student_id",
            "student_count_for_owner": None,
            "legacy_record_count": 0,
            "international": intl,
            "huaqiao": hq,
            "records": items,
        }

    siblings = (
        db.query(StudentMasterProfile)
        .filter(
            StudentMasterProfile.user_id == student.user_id,
            StudentMasterProfile.status != "DELETED",
        )
        .count()
    )
    legacy = (
        db.query(EligibilityRecord)
        .filter(EligibilityRecord.user_id == student.user_id, EligibilityRecord.student_id.is_(None))
        .order_by(EligibilityRecord.created_at.desc())
        .limit(50)
        .all()
    )

    if siblings > 1:
        return {
            "mapping_status": "UNRESOLVED",
            "message": "历史资格记录尚未绑定到具体学生",
            "reason": "owner_has_multiple_students",
            "student_count_for_owner": siblings,
            "legacy_record_count": len(legacy),
            "international": None,
            "huaqiao": None,
            "records": [],
        }

    if siblings == 1 and legacy:
        items = [_ser_eligibility(r, "LEGACY_USER_SCOPED") for r in legacy]
        intl = next((x for x in items if x["eligibility_type"] == "international"), None)
        hq = next((x for x in items if x["eligibility_type"] in ("huaqiao", "overseas_chinese")), None)
        return {
            "mapping_status": "LEGACY_USER_SCOPED",
            "message": "资格记录按 user_id 关联；当前用户仅有一名学生，只读回退展示。",
            "student_count_for_owner": 1,
            "legacy_record_count": len(legacy),
            "international": intl,
            "huaqiao": hq,
            "records": items,
        }

    return {
        "mapping_status": "EMPTY",
        "message": "无历史资格记录",
        "student_count_for_owner": siblings,
        "legacy_record_count": 0,
        "international": None,
        "huaqiao": None,
        "records": [],
    }


def _map_consultations(db: Session, student: StudentMasterProfile) -> dict:
    student_rows = ai.list_for_student(db, student.id)
    siblings = (
        db.query(StudentMasterProfile)
        .filter(
            StudentMasterProfile.user_id == student.user_id,
            StudentMasterProfile.status != "DELETED",
        )
        .count()
    )
    legacy = (
        db.query(ExpertConsultation)
        .filter(ExpertConsultation.user_id == student.user_id, ExpertConsultation.student_id.is_(None))
        .order_by(ExpertConsultation.created_at.desc())
        .limit(50)
        .all()
    )
    legacy_out = []
    legacy_status = "EMPTY"
    if siblings > 1 and legacy:
        legacy_status = "UNRESOLVED"
    elif siblings == 1 and legacy:
        legacy_status = "LEGACY_USER_SCOPED"
        legacy_out = [
            {
                "id": r.id,
                "title": r.title,
                "status": r.status,
                "student_id": None,
                "mapping_status": "LEGACY_USER_SCOPED",
                "report_kind": r.report_kind or "",
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "published_at": r.published_at.isoformat() if r.published_at else None,
            }
            for r in legacy
        ]
    elif siblings > 1:
        legacy_status = "UNRESOLVED"

    return {
        "mapping_status": "STUDENT_SCOPED" if student_rows else legacy_status,
        "message": "student_id 绑定咨询优先；多学生时不猜测 legacy user 级记录",
        "consultations": student_rows,
        "ai_drafts": student_rows,  # alias for UI
        "db_consultations": legacy_out,
        "legacy_mapping_status": legacy_status,
    }


def _timeline_for(db: Session, student_id: int) -> list[dict]:
    rows = db.query(StudentTimelineItem).filter(StudentTimelineItem.student_id == student_id).all()
    for t in rows:
        if t.student_id != student_id:
            raise HTTPException(status_code=500, detail="timeline isolation violation")
    rows.sort(key=lambda r: ((r.deadline.isoformat() if r.deadline else "9999-12-31"), r.id or 0))
    return [serialize_item(t) for t in rows]


@router.get("/contract")
def contract(_: User = Depends(require_admin_console)):
    return {"contract": ADMIN_V1_CONTRACT, "version": "v1-phase3"}


@router.get("/me")
def admin_me(admin: User = Depends(require_admin_console)):
    console = resolve_console_role(admin)
    return {
        "user": _user_brief(admin),
        "console_role": console.value if console else None,
        "rbac": rbac_proposal(),
        "ai_provider": ai.provider_status(),
        "contract": ADMIN_V1_CONTRACT,
    }


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
        .filter(
            ExpertConsultation.status.in_(
                ["draft_ready", "pending_ai", "pending_review", ai.STATUS_DRAFT, ai.STATUS_REVIEWED, ai.STATUS_APPROVED]
            )
        )
        .count()
    )
    recent = db.query(ExpertConsultation).order_by(ExpertConsultation.created_at.desc()).limit(10).all()
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
                "student_id": r.student_id,
                "title": r.title,
                "status": r.status,
                "report_kind": r.report_kind,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in recent
        ],
        "bi": "simple_v1",
    }


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
    return {"user": brief, "students": [public_student_meta(s) for s in students]}


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
    row = _get_student_or_404(db, student_id)
    owner = db.query(User).filter(User.id == row.user_id).first()
    role = _console_role_str(admin)
    raw = _decrypt_student_profile(row)
    profile = redact_profile_for_admin(raw, role="support" if role == "support" else "consultant")
    assert "cipher_blob" not in profile

    eligibility = _map_eligibility(db, row)
    consultations = _map_consultations(db, row)
    timeline = _timeline_for(db, student_id)

    admin_audit.record_audit(
        db,
        actor_user_id=admin.id,
        action=admin_audit.VIEW_STUDENT,
        resource_type="student_master_profile",
        resource_id=student_id,
        student_id=student_id,
        metadata={"view": "student_360"},
    )

    return {
        "student_id": student_id,
        "meta": public_student_meta(row),
        "owner": _user_brief(owner),
        "sections": {
            "basic_info": profile.get("basic_info") or {},
            "identity": profile.get("identity") or {},
            "education": profile.get("education") or {},
            "language_exams": (profile.get("courses") or {}).get("language_exams") or [],
            "goals": profile.get("goals") or {},
            "planning": profile.get("planning") or {},
            "summary": profile.get("summary") or profile_summary(raw),
        },
        "eligibility": eligibility,
        "timeline": timeline,
        "consultations": consultations,
        "consultant_notes": {
            "placeholder": True,
            "notes": [],
            "message": "顾问备注将在后续阶段持久化",
        },
        "privacy": profile.get("_privacy") or {"masked": True},
        "ai_provider": ai.provider_status(),
        "report_kinds": ai.REPORT_KINDS,
    }


@router.get("/students/{student_id}/timeline")
def student_timeline(
    student_id: int,
    admin: User = Depends(require_capability("admin.student360.read")),
    db: Session = Depends(get_db),
):
    _get_student_or_404(db, student_id)
    return {"student_id": student_id, "timeline": _timeline_for(db, student_id)}


@router.get("/students/{student_id}/eligibility")
def student_eligibility(
    student_id: int,
    admin: User = Depends(require_capability("admin.student360.read")),
    db: Session = Depends(get_db),
):
    row = _get_student_or_404(db, student_id)
    return {"student_id": student_id, **_map_eligibility(db, row)}


@router.get("/students/{student_id}/consultations")
def student_consultations(
    student_id: int,
    admin: User = Depends(require_capability("admin.student360.read")),
    db: Session = Depends(get_db),
):
    row = _get_student_or_404(db, student_id)
    return {"student_id": student_id, **_map_consultations(db, row)}


# ---------------------------------------------------------------------------
# AI Expert — frozen ai-drafts contract
# ---------------------------------------------------------------------------

class AiDraftCreateIn(BaseModel):
    report_kind: str = Field(..., description="One of REPORT_KINDS")
    submit_review: bool = False


class AiDraftPatchIn(BaseModel):
    content: str | None = None
    payload: dict | None = None
    submit_review: bool = True


@router.get("/students/{student_id}/ai-drafts")
def list_ai_drafts(
    student_id: int,
    admin: User = Depends(require_capability("admin.ai.generate")),
    db: Session = Depends(get_db),
):
    _get_student_or_404(db, student_id)
    drafts = ai.list_for_student(db, student_id)
    return {
        "student_id": student_id,
        "drafts": drafts,
        "report_kinds": ai.REPORT_KINDS,
        "ai_provider": ai.provider_status(),
    }


@router.post("/students/{student_id}/ai-drafts")
async def create_ai_draft(
    student_id: int,
    body: AiDraftCreateIn,
    admin: User = Depends(require_capability("admin.ai.generate")),
    db: Session = Depends(get_db),
):
    row = _get_student_or_404(db, student_id)
    if row.id != student_id:
        raise HTTPException(status_code=500, detail="student_id isolation violation")
    profile = _decrypt_student_profile(row)
    timeline = _timeline_for(db, student_id)
    eligibility = _map_eligibility(db, row)
    try:
        draft = await ai.create_ai_draft(
            db,
            student=row,
            report_kind=body.report_kind,
            profile=profile,
            actor=admin,
            timeline=timeline,
            eligibility=eligibility,
            mark_reviewed=body.submit_review,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    admin_audit.record_audit(
        db,
        actor_user_id=admin.id,
        action=admin_audit.AI_GENERATE,
        resource_type="expert_consultation",
        resource_id=draft["id"],
        student_id=student_id,
        metadata={"report_kind": body.report_kind, "status": draft["status"], "provider": draft.get("ai_provider")},
    )
    return {
        "student_id": student_id,
        "draft": draft,
        "flow": "AI_GENERATE→DRAFT→REVIEWED→APPROVED→PUBLISHED",
    }


@router.patch("/students/{student_id}/ai-drafts/{draft_id}")
def patch_ai_draft(
    student_id: int,
    draft_id: int,
    body: AiDraftPatchIn,
    admin: User = Depends(require_capability("admin.ai.edit")),
    db: Session = Depends(get_db),
):
    _get_student_or_404(db, student_id)
    try:
        updated = ai.edit_draft(
            db,
            student_id=student_id,
            draft_id=draft_id,
            actor=admin,
            content=body.content,
            payload=body.payload,
            mark_reviewed=body.submit_review,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="草稿不存在") from None
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    admin_audit.record_audit(
        db,
        actor_user_id=admin.id,
        action=admin_audit.AI_EDIT,
        resource_type="expert_consultation",
        resource_id=draft_id,
        student_id=student_id,
        metadata={"status": updated["status"]},
    )
    return {"student_id": student_id, "draft": updated}


@router.post("/students/{student_id}/ai-drafts/{draft_id}/approve")
def approve_ai_draft(
    student_id: int,
    draft_id: int,
    admin: User = Depends(require_capability("admin.ai.approve")),
    db: Session = Depends(get_db),
):
    _get_student_or_404(db, student_id)
    try:
        updated = ai.approve_draft(db, student_id=student_id, draft_id=draft_id, actor=admin)
    except KeyError:
        raise HTTPException(status_code=404, detail="草稿不存在") from None
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    assert updated["published"] is False
    admin_audit.record_audit(
        db,
        actor_user_id=admin.id,
        action=admin_audit.AI_APPROVE,
        resource_type="expert_consultation",
        resource_id=draft_id,
        student_id=student_id,
        metadata={"status": updated["status"]},
    )
    return {"student_id": student_id, "draft": updated}


@router.post("/students/{student_id}/ai-drafts/{draft_id}/publish")
def publish_ai_draft(
    student_id: int,
    draft_id: int,
    admin: User = Depends(require_capability("admin.ai.publish")),
    db: Session = Depends(get_db),
):
    """Publish only APPROVED drafts bound to this student_id. Never auto from AI."""
    _get_student_or_404(db, student_id)
    try:
        updated = ai.publish_draft(db, student_id=student_id, draft_id=draft_id, actor=admin)
    except KeyError:
        raise HTTPException(status_code=404, detail="草稿不存在") from None
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    admin_audit.record_audit(
        db,
        actor_user_id=admin.id,
        action=admin_audit.AI_PUBLISH,
        resource_type="expert_consultation",
        resource_id=draft_id,
        student_id=student_id,
        metadata={"status": updated["status"]},
    )
    return {"student_id": student_id, "draft": updated}


@router.get("/settings")
def settings_view(admin: User = Depends(require_capability("admin.settings"))):
    return {
        "admin_domain": "https://admin.guoqiaoplan.com",
        "rbac": rbac_proposal(),
        "ai_provider": ai.provider_status(),
        "contract": ADMIN_V1_CONTRACT,
        "migration_status": {
            "draft_file": "alembic/drafts/007_admin_ai_expert_v1_NOT_APPLIED.py",
            "applied": False,
            "production_db_changed": False,
        },
    }
