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
from .services import notifications as notif
from .services import admin_audit
from .services.admin_privacy import public_student_meta, redact_profile_for_admin
from .services.admin_rbac import (
    AdminConsoleRole,
    capabilities_for,
    consultant_scoped,
    menu_for,
    rbac_proposal,
    require_admin_console,
    require_capability,
    resolve_console_role,
)
from .services.admin_rbac import ROLE_LABEL_ZH
from .services.membership_trial import is_trial_plan, trial_info
from .services.security import is_paid
from .services.student_profile import empty_profile, normalize_profile, profile_summary
from .services import student_crm as crm
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
    "GET /api/admin/v1/staff",
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
        "account_kind": getattr(u, "account_kind", None) or ("STAFF" if (u.role or "") in {"admin", "super_admin", "operations_admin", "consultant", "support"} else "CUSTOMER"),
        "job_title": getattr(u, "job_title", None) or "",
        "last_login_at": u.last_login_at.isoformat() if getattr(u, "last_login_at", None) else None,
        "must_change_password": bool(getattr(u, "must_change_password", False)),
    }


def _assert_student_visible(admin: User, row: StudentMasterProfile, *, write: bool = False) -> None:
    role = resolve_console_role(admin)
    if consultant_scoped(admin) and row.assignee_user_id != admin.id:
        raise HTTPException(status_code=403, detail="只能查看分配给自己的学生")
    if write and role == AdminConsoleRole.SUPPORT:
        raise HTTPException(status_code=403, detail="客服不能修改学生档案")


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
        "role_label": ROLE_LABEL_ZH.get(console.value if console else "", ""),
        "permissions": capabilities_for(admin),
        "menu": menu_for(admin),
        "must_change_password": bool(getattr(admin, "must_change_password", False)),
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
    scoped_assignee = admin.id if consultant_scoped(admin) else None
    role = resolve_console_role(admin)
    my_students = None
    if scoped_assignee:
        my_students = (
            db.query(StudentMasterProfile)
            .filter(
                StudentMasterProfile.assignee_user_id == admin.id,
                StudentMasterProfile.status != "DELETED",
            )
            .count()
        )
    return {
        "dashboard_role": role.value if role else None,
        "scope": "assignee" if scoped_assignee else "org",
        "my_students": my_students,
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
        "crm_todos": crm.dashboard_crm_todos(db, assignee_user_id=scoped_assignee),
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
        if (u.role or "").lower() in {"admin", "super_admin", "operations_admin", "consultant", "support"}:
            continue
        if (getattr(u, "account_kind", None) or "").upper() == "STAFF":
            continue
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
    assignee_user_id: int | None = Query(None),
    crm_stage: str | None = Query(None),
    risk_level: str | None = Query(None),
    identity_track: str | None = Query(None),
    plan: str | None = Query(None, description="trial|paid|any"),
    entry_year: str | None = Query(None),
    sort: str = Query("updated_at", description="updated_at|last_follow_up|next_follow_up|created_at"),
    admin: User = Depends(require_capability("admin.students.read")),
    db: Session = Depends(get_db),
):
    """Student CRM list V2 — operational columns; never returns cipher_blob."""
    query = db.query(StudentMasterProfile).filter(StudentMasterProfile.status != "DELETED")
    if consultant_scoped(admin):
        assignee_user_id = admin.id
    if assignee_user_id is not None:
        if assignee_user_id == 0:
            query = query.filter(StudentMasterProfile.assignee_user_id.is_(None))
        else:
            query = query.filter(StudentMasterProfile.assignee_user_id == assignee_user_id)
    if crm_stage:
        query = query.filter(StudentMasterProfile.crm_stage == crm_stage.upper())
    if risk_level:
        query = query.filter(StudentMasterProfile.risk_level == risk_level.upper())
    if identity_track:
        query = query.filter(StudentMasterProfile.identity_track == identity_track)

    sort_key = (sort or "updated_at").lower()
    if sort_key == "last_follow_up":
        query = query.order_by(StudentMasterProfile.last_follow_up_at.is_(None), StudentMasterProfile.last_follow_up_at.desc())
    elif sort_key == "next_follow_up":
        query = query.order_by(StudentMasterProfile.next_follow_up_at.is_(None), StudentMasterProfile.next_follow_up_at.asc())
    elif sort_key == "created_at":
        query = query.order_by(StudentMasterProfile.created_at.desc())
    else:
        query = query.order_by(StudentMasterProfile.updated_at.desc())

    rows = query.limit(500).all()
    items = []
    for s in rows:
        owner = db.query(User).filter(User.id == s.user_id).first()
        meta = public_student_meta(s)
        meta["owner"] = {"id": owner.id, "email": owner.email, "name": owner.name} if owner else None
        if owner:
            from .services.membership_trial import trial_info as _trial_info
            from .services.security import is_paid as _is_paid
            t = _trial_info(owner)
            meta["owner_plan"] = {
                "plan_code": owner.plan_code,
                "is_paid": _is_paid(owner),
                "trial_active": bool(t.get("trial_active")),
            }
        else:
            meta["owner_plan"] = {}
        try:
            prof = _decrypt_student_profile(s)
            # Soft-heal display_name when cipher already has a real name
            summary = profile_summary(prof)
            targets = summary.get("target_universities") or []
            meta["goal_hint"] = "、".join([t for t in targets if t][:3])
            meta["summary"] = {
                "chinese_name": summary.get("chinese_name") or "",
                "intended_entry_year": summary.get("intended_entry_year") or "",
                "international_status": summary.get("international_status") or "",
                "huaqiao_status": summary.get("huaqiao_status") or "",
            }
            snap = crm.crm_snapshot(db, s, prof)
        except HTTPException:
            meta["goal_hint"] = ""
            meta["summary"] = {}
            snap = crm.crm_snapshot(db, s, None)

        meta["display_name"] = snap["display_name"]
        meta["display_name_needs_repair"] = snap["display_name_needs_repair"]
        meta["crm"] = snap
        meta["assignee_label"] = snap["assignee_label"]
        meta["crm_stage"] = snap["crm_stage"]
        meta["crm_stage_label"] = snap["crm_stage_label"]
        meta["risk_level"] = snap["risk_level"]
        meta["next_action"] = snap["next_action"]
        meta["next_follow_up_at"] = snap["next_follow_up_at"]
        meta["last_follow_up_at"] = snap["last_follow_up_at"]
        meta["identity_track"] = snap["identity_track"]
        meta["target_universities"] = snap["target_universities"]
        meta["intended_entry_year"] = snap["intended_entry_year"]

        if entry_year and str(snap.get("intended_entry_year") or "") != str(entry_year):
            continue
        if plan == "trial" and not (meta.get("owner_plan") or {}).get("trial_active"):
            continue
        if plan == "paid" and not (meta.get("owner_plan") or {}).get("is_paid"):
            continue
        if q:
            ql = q.lower()
            blob = f"{meta.get('display_name')}{meta.get('summary')}{owner.email if owner else ''}{s.id}{snap.get('assignee_label')}".lower()
            if ql not in blob:
                continue
        # Privacy: never include cipher / docs
        assert "cipher_blob" not in meta
        items.append(meta)
    return {"students": items, "count": len(items), "crm_stages": list(crm.CRM_STAGES), "stage_labels": crm.CRM_STAGE_LABELS_ZH}



@router.get("/students/{student_id}")
def student_360(
    student_id: int,
    admin: User = Depends(require_capability("admin.student360.read")),
    db: Session = Depends(get_db),
):
    row = _get_student_or_404(db, student_id)
    _assert_student_visible(admin, row, write=False)
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
            "csca": profile.get("csca") or {},
            "goals": profile.get("goals") or {},
            "planning": profile.get("planning") or {},
            "summary": profile.get("summary") or profile_summary(raw),
        },
        "csca_card": __import__("app.services.csca", fromlist=["csca_card"]).csca_card(profile.get("csca")),
        "eligibility": eligibility,
        "timeline": timeline,
        "consultations": consultations,
        "crm": (_crm := crm.crm_snapshot(db, row, raw)),
        "crm_stage_labels": crm.CRM_STAGE_LABELS_ZH,
        "follow_ups": crm.list_follow_ups(db, student_id, limit=30),
        "ops_header": {
            "assignee_label": _crm.get("assignee_label"),
            "crm_stage_label": _crm.get("crm_stage_label"),
            "next_action": _crm.get("next_action"),
            "next_follow_up_at": _crm.get("next_follow_up_at"),
            "display_name": _crm.get("display_name"),
        },
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
    row = _get_student_or_404(db, student_id)
    _assert_student_visible(admin, row, write=False)
    return {"student_id": student_id, "timeline": _timeline_for(db, student_id)}


@router.get("/students/{student_id}/eligibility")
def student_eligibility(
    student_id: int,
    admin: User = Depends(require_capability("admin.student360.read")),
    db: Session = Depends(get_db),
):
    row = _get_student_or_404(db, student_id)
    _assert_student_visible(admin, row, write=False)
    return {"student_id": student_id, **_map_eligibility(db, row)}


@router.get("/students/{student_id}/consultations")
def student_consultations(
    student_id: int,
    admin: User = Depends(require_capability("admin.student360.read")),
    db: Session = Depends(get_db),
):
    row = _get_student_or_404(db, student_id)
    _assert_student_visible(admin, row, write=False)
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
    row = _get_student_or_404(db, student_id)
    _assert_student_visible(admin, row, write=False)
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
    _assert_student_visible(admin, row, write=False)
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
    try:
        notif.notify_admins_ai_review_required(db, student=row, draft=draft, actor=admin)
    except Exception:
        pass  # notification failure must not block AI draft creation
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
    row = _get_student_or_404(db, student_id)
    _assert_student_visible(admin, row, write=False)
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
    row = _get_student_or_404(db, student_id)
    _assert_student_visible(admin, row, write=False)
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
    row = _get_student_or_404(db, student_id)
    _assert_student_visible(admin, row, write=False)
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
    try:
        student = _get_student_or_404(db, student_id)
        notif.notify_student_report_published(db, student=student, draft=updated)
    except Exception:
        pass
    return {"student_id": student_id, "draft": updated}


@router.get("/settings")
def settings_view(admin: User = Depends(require_capability("settings.read"))):
    return {
        "admin_domain": "https://admin.guoqiaoplan.com",
        "rbac": rbac_proposal(),
        "ai_provider": ai.provider_status(),
        "contract": ADMIN_V1_CONTRACT,
        "migration_status": {
            "alembic_head_code": "011_admin_console_v2",
            "production_expected": "010_student_crm_v1",
            "applied": False,
            "production_db_changed": False,
        },
    }



class AdminCscaPatch(BaseModel):
    csca_status: str | None = None
    csca_exam_date: str | None = None
    csca_registration_deadline: str | None = None
    csca_result_date: str | None = None
    csca_score: str | None = None
    csca_level: str | None = None
    csca_notes: str | None = None


@router.patch("/students/{student_id}/csca")
def update_student_csca(
    student_id: int,
    payload: AdminCscaPatch,
    admin: User = Depends(require_capability("admin.student360.write")),
    db: Session = Depends(get_db),
):
    """Admin assist update for CSCA section. Requires audit. Never invents dates."""
    from datetime import datetime as _dt

    from .services.csca import csca_card, normalize_csca, sync_csca_timeline, _now_iso
    from .services.student_profile import display_name_of, normalize_profile
    from .services.vault_crypto import encrypt_profile_json

    row = _get_student_or_404(db, student_id)
    _assert_student_visible(admin, row, write=True)
    raw = _decrypt_student_profile(row)
    current = normalize_csca(raw.get("csca"))
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        if v is not None:
            current[k] = v
    # Admin-entered dates get source=admin when provided
    if "csca_registration_deadline" in data and data["csca_registration_deadline"]:
        current["registration_deadline_source"] = "admin"
    if "csca_exam_date" in data and data["csca_exam_date"]:
        current["exam_date_source"] = "admin"
    if "csca_result_date" in data and data["csca_result_date"]:
        current["result_date_source"] = "admin"
    current = normalize_csca(current)
    current["updated_at"] = _now_iso()
    raw["csca"] = current
    doc = normalize_profile(raw)
    row.cipher_blob = encrypt_profile_json(doc)
    row.display_name = display_name_of(doc)
    row.updated_at = _dt.utcnow()
    db.add(row)
    db.commit()
    db.refresh(row)

    sync = sync_csca_timeline(
        db,
        student_id=row.id,
        user_id=row.user_id,
        tenant_id=row.tenant_id,
        csca=current,
        commit=True,
    )
    admin_audit.record_audit(
        db,
        actor_user_id=admin.id,
        action=admin_audit.CSCA_UPDATE,
        resource_type="student_master_profile",
        resource_id=student_id,
        student_id=student_id,
        metadata={
            "view": "student_360_csca",
            "csca_status": current.get("csca_status"),
            "fields": sorted(data.keys()),
            "timeline_sync": {k: sync.get(k) for k in ("created", "updated", "removed")},
        },
    )
    card = csca_card(current)
    assert "cipher_blob" not in card
    return {
        "student_id": student_id,
        "csca": current,
        "csca_card": card,
        "timeline_sync": sync,
        "fake_date_allowed": False,
    }


# ---------------------------------------------------------------------------
# Student CRM V1
# ---------------------------------------------------------------------------

class AssignStudentIn(BaseModel):
    assignee_user_id: int | None = None


class CrmPatchIn(BaseModel):
    crm_stage: str | None = None
    risk_level: str | None = None
    next_action: str | None = None
    next_follow_up_at: str | None = None
    identity_track: str | None = None
    display_name: str | None = None


class FollowUpCreateIn(BaseModel):
    content: str = Field(..., min_length=1)
    summary: str = ""
    type: str = "NOTE"
    source: str = "HUMAN"
    next_action: str | None = None
    next_follow_up_at: str | None = None


@router.get("/staff")
def list_staff(admin: User = Depends(require_capability("admin.students.read")), db: Session = Depends(get_db)):
    return {"staff": crm.list_staff_candidates(db)}



@router.post("/students/{student_id}/assign")
def assign_student_endpoint(
    student_id: int,
    payload: AssignStudentIn,
    admin: User = Depends(require_capability("students.assign")),
    db: Session = Depends(get_db),
):
    row = _get_student_or_404(db, student_id)
    _assert_student_visible(admin, row, write=True)
    try:
        snap = crm.assign_student(db, row=row, assignee_user_id=payload.assignee_user_id, operator=admin)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"student_id": student_id, "crm": snap}


@router.patch("/students/{student_id}/crm")
def patch_student_crm(
    student_id: int,
    payload: CrmPatchIn,
    admin: User = Depends(require_capability("admin.student360.write")),
    db: Session = Depends(get_db),
):
    row = _get_student_or_404(db, student_id)
    _assert_student_visible(admin, row, write=True)
    try:
        snap = crm.patch_crm_fields(
            db,
            row=row,
            operator=admin,
            crm_stage=payload.crm_stage,
            risk_level=payload.risk_level,
            next_action=payload.next_action,
            next_follow_up_at=payload.next_follow_up_at if payload.next_follow_up_at is not None else ...,
            identity_track=payload.identity_track,
            display_name_override=payload.display_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"student_id": student_id, "crm": snap}


@router.get("/students/{student_id}/follow-ups")
def get_follow_ups(
    student_id: int,
    admin: User = Depends(require_capability("admin.student360.read")),
    db: Session = Depends(get_db),
):
    row = _get_student_or_404(db, student_id)
    _assert_student_visible(admin, row, write=False)
    return {"student_id": student_id, "follow_ups": crm.list_follow_ups(db, student_id)}


@router.post("/students/{student_id}/follow-ups")
def post_follow_up(
    student_id: int,
    payload: FollowUpCreateIn,
    admin: User = Depends(require_capability("followups.write")),
    db: Session = Depends(get_db),
):
    row = _get_student_or_404(db, student_id)
    _assert_student_visible(admin, row, write=False)
    nxt = None
    if payload.next_follow_up_at:
        nxt = datetime.fromisoformat(payload.next_follow_up_at.replace("Z", ""))
    try:
        item = crm.create_follow_up(
            db,
            row=row,
            operator=admin,
            content=payload.content,
            summary=payload.summary,
            type_=payload.type,
            source=payload.source,
            next_action=payload.next_action,
            next_follow_up_at=nxt,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"student_id": student_id, "follow_up": item, "crm": crm.crm_snapshot(db, row)}


@router.post("/students/{student_id}/ai-follow-up-drafts")
def ai_follow_up_drafts(
    student_id: int,
    admin: User = Depends(require_capability("admin.student360.read")),
    db: Session = Depends(get_db),
):
    """AI follow-up suggestions — DRAFT only, never auto-send."""
    row = _get_student_or_404(db, student_id)
    _assert_student_visible(admin, row, write=False)
    raw = _decrypt_student_profile(row)
    snap = crm.crm_snapshot(db, row, raw)
    drafts = crm.ai_follow_up_drafts(student_id=student_id, crm=snap)
    assert all(d.get("auto_send") is False for d in drafts)
    assert all(d.get("source") == "AI_ASSISTED" for d in drafts)
    return {"student_id": student_id, "drafts": drafts, "auto_send": False}
