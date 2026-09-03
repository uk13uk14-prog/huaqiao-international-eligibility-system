"""Student Master Profile HTTP API. Eligibility engines are not modified."""
from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from .models import AdmissionSchedule, CustomerVault, StudentMasterProfile, StudentTimelineItem, University, User
from .schemas import (
    StudentCreateIn,
    StudentEligibilityWriteback,
    StudentSectionPatch,
    StudentTimelineManualCreate,
    StudentTimelinePatch,
)
from .services.security import get_current_user
from .services.student_portrait import StudentPortraitService
from .services.student_profile_entitlements import student_profile_entitlements
from .services.student_profile import (
    SECTIONS,
    apply_eligibility_result,
    completeness,
    display_name_of,
    empty_profile,
    judge_prefills,
    merge_section,
    migrate_legacy_vault,
    normalize_profile,
    profile_summary,
    project_legacy_vault,
)
from .services.student_timeline import (
    TIMELINE_STATUSES,
    compute_status,
    group_timeline,
    regenerate_student_timeline,
    serialize_item,
    timeline_summary,
)
from .services.vault_crypto import decrypt_profile_json, encrypt_profile_json

router = APIRouter(prefix="/api/students", tags=["students"])
portrait_service = StudentPortraitService()


def _decrypt_row(row: StudentMasterProfile) -> dict:
    if not row.cipher_blob:
        return empty_profile()
    try:
        return normalize_profile(decrypt_profile_json(row.cipher_blob))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="学生档案解密失败，请联系管理员") from exc


def _sync_legacy_vault(db: Session, user_id: int, profile: dict) -> None:
    vault = db.query(CustomerVault).filter(CustomerVault.user_id == user_id).first()
    if not vault:
        return
    try:
        current = decrypt_profile_json(vault.cipher_blob) if vault.cipher_blob else {}
    except Exception:
        current = {}
    if not isinstance(current, dict):
        current = {}
    projected = project_legacy_vault(profile)
    merged = {**current, **projected}
    vault.cipher_blob = encrypt_profile_json(merged)
    vault.schema_version = max(int(vault.schema_version or 1), 2)
    db.add(vault)
    db.commit()


def _save_row(db: Session, row: StudentMasterProfile, profile: dict) -> StudentMasterProfile:
    doc = normalize_profile(profile)
    row.cipher_blob = encrypt_profile_json(doc)
    row.display_name = display_name_of(doc)
    row.schema_version = 2
    row.updated_at = datetime.utcnow()
    db.add(row)
    db.commit()
    db.refresh(row)
    _sync_legacy_vault(db, row.user_id, doc)
    return row


def _timeline_items_for(db: Session, student_id: int, user_id: int) -> list[dict]:
    rows = (
        db.query(StudentTimelineItem)
        .filter(StudentTimelineItem.student_id == student_id, StudentTimelineItem.user_id == user_id)
        .all()
    )
    rows.sort(key=lambda r: ((r.deadline or date.max), r.id or 0))
    return [serialize_item(r) for r in rows]


def _payload(row: StudentMasterProfile, profile: dict | None = None, db: Session | None = None) -> dict:
    doc = profile if profile is not None else _decrypt_row(row)
    tl_summary = None
    if db is not None:
        items = _timeline_items_for(db, row.id, row.user_id)
        tl_summary = timeline_summary(items)
    portrait = portrait_service.generate(doc, tl_summary)
    return {
        "id": row.id,
        "display_name": row.display_name or display_name_of(doc),
        "schema_version": row.schema_version,
        "source": row.source,
        "status": getattr(row, "status", None) or "ACTIVE",
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "archived_at": getattr(row, "archived_at", None),
        "deleted_at": getattr(row, "deleted_at", None),
        "profile": doc,
        "summary": profile_summary(doc),
        "completeness": completeness(doc),
        "legacy_projection": project_legacy_vault(doc),
        "judge_prefills": judge_prefills(doc),
        "portrait": portrait,
        "dashboard": {
            "completeness": completeness(doc),
            "portrait_basic": portrait["basic"],
            "identity": portrait["identity"],
            "academic_summary": {
                "curricula": portrait["academic"]["curricula"],
                "strengths": portrait["academic"]["academic_strengths"][:3],
                "weaknesses": portrait["academic"]["academic_weaknesses"][:3],
                "missing": portrait["academic"]["missing_academic_data"],
            },
            "language_summary": portrait["language"]["summary"],
            "targets": portrait["targets"]["counts"],
            "application_readiness": portrait["application_readiness"],
            "risk_flags": portrait["risk_flags"],
            "next_actions": portrait["next_actions"],
            "timeline_summary": portrait["timeline_summary"],
        },
    }


def _owned(db: Session, user: User, student_id: int, *, allow_deleted: bool = False) -> StudentMasterProfile:
    row = (
        db.query(StudentMasterProfile)
        .filter(
            StudentMasterProfile.id == student_id,
            StudentMasterProfile.user_id == user.id,
            StudentMasterProfile.tenant_id == user.tenant_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="学生档案不存在")
    status = getattr(row, "status", None) or "ACTIVE"
    if status == "DELETED" and not allow_deleted:
        raise HTTPException(status_code=404, detail="学生档案不存在")
    return row


def migrate_vault_if_needed(db: Session, user: User) -> None:
    existing = db.query(StudentMasterProfile).filter(StudentMasterProfile.user_id == user.id).count()
    if existing:
        return
    vault = db.query(CustomerVault).filter(CustomerVault.user_id == user.id).first()
    if not vault or not vault.cipher_blob:
        return
    try:
        old = decrypt_profile_json(vault.cipher_blob)
    except Exception:
        return
    if not old:
        return
    # Legacy migration creates the first seat — still respect entitlement.
    try:
        student_profile_entitlements.assert_can_create(db, user)
    except HTTPException:
        return
    profile = migrate_legacy_vault(old)
    row = StudentMasterProfile(
        user_id=user.id,
        tenant_id=user.tenant_id,
        display_name=display_name_of(profile),
        cipher_blob=encrypt_profile_json(profile),
        schema_version=2,
        source="legacy_vault",
        status="ACTIVE",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    vault.schema_version = max(int(vault.schema_version or 1), 2)
    db.commit()


@router.get("")
def list_students(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    migrate_vault_if_needed(db, user)
    rows = (
        db.query(StudentMasterProfile)
        .filter(
            StudentMasterProfile.user_id == user.id,
            StudentMasterProfile.status != "DELETED",
        )
        .order_by(StudentMasterProfile.updated_at.desc())
        .all()
    )
    items = []
    for row in rows:
        doc = _decrypt_row(row)
        items.append(
            {
                "id": row.id,
                "display_name": row.display_name or display_name_of(doc),
                "source": row.source,
                "status": getattr(row, "status", None) or "ACTIVE",
                "updated_at": row.updated_at,
                "summary": profile_summary(doc),
                "completeness": completeness(doc),
                "application_readiness": portrait_service.generate(doc, timeline_summary(_timeline_items_for(db, row.id, user.id)))["application_readiness"]["score"],
            }
        )
    slots = student_profile_entitlements.usage(db, user)
    return {"students": items, "slots": slots}


@router.post("")
def create_student(payload: StudentCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    student_profile_entitlements.assert_can_create(db, user)
    incoming = payload.profile or {}
    if incoming.get("basic_info") or incoming.get("schema_version") == 2:
        profile = normalize_profile(incoming)
    else:
        profile = migrate_legacy_vault(incoming) if incoming else empty_profile()
    if payload.wizard:
        profile["wizard_completed"] = False
    row = StudentMasterProfile(
        user_id=user.id,
        tenant_id=user.tenant_id,
        display_name=display_name_of(profile),
        cipher_blob=encrypt_profile_json(profile),
        schema_version=2,
        source="created",
        status="ACTIVE",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    out = _payload(row, profile, db)
    out["slots"] = student_profile_entitlements.usage(db, user)
    return out


@router.get("/meta")
def student_meta():
    from .services.student_profile import (
        CURRICULUMS,
        GRADE_TYPES,
        LANGUAGE_EXAMS,
        OTHER_EXAM_TYPES,
        PRIORITY_LEVELS,
        SCHOOL_TYPES,
        ELIGIBILITY_STATUSES,
        SECTION_NOTES,
    )

    return {
        "school_types": SCHOOL_TYPES,
        "curriculums": CURRICULUMS,
        "grade_types": GRADE_TYPES,
        "language_exams": LANGUAGE_EXAMS,
        "other_exam_types": OTHER_EXAM_TYPES,
        "priority_levels": PRIORITY_LEVELS,
        "eligibility_statuses": ELIGIBILITY_STATUSES,
        "section_notes": SECTION_NOTES,
        "sections": SECTIONS,
    }


@router.get("/{student_id}")
def get_student(student_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = _owned(db, user, student_id)
    out = _payload(row, db=db)
    out["slots"] = student_profile_entitlements.usage(db, user)
    return out


@router.post("/{student_id}/archive")
def archive_student(student_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = _owned(db, user, student_id)
    row.status = "ARCHIVED"
    row.archived_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "status": row.status,
        "archived_at": row.archived_at,
        "slots": student_profile_entitlements.usage(db, user),
    }


@router.post("/{student_id}/soft-delete")
def soft_delete_student(student_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Soft delete — still consumes a seat; does not hard-delete data."""
    row = _owned(db, user, student_id)
    row.status = "DELETED"
    row.deleted_at = datetime.utcnow()
    row.updated_at = datetime.utcnow()
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "status": row.status,
        "deleted_at": row.deleted_at,
        "slots": student_profile_entitlements.usage(db, user),
        "note": "软删除档案仍计入当前套餐学生档案席位，无法通过删除绕过额度限制。",
    }


@router.patch("/{student_id}/sections/{section}")
def patch_section(
    student_id: int,
    section: str,
    payload: StudentSectionPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if section not in SECTIONS:
        raise HTTPException(status_code=400, detail="未知档案分节")
    row = _owned(db, user, student_id)
    profile = merge_section(_decrypt_row(row), section, payload.data or {})
    if section == "basic_info" and (profile["basic_info"].get("chinese_name") or profile["basic_info"].get("english_name")):
        profile["wizard_completed"] = profile.get("wizard_completed") or False
    _save_row(db, row, profile)
    return _payload(row, profile, db)


@router.post("/{student_id}/complete-wizard")
def complete_wizard(student_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = _owned(db, user, student_id)
    profile = _decrypt_row(row)
    profile["wizard_completed"] = True
    _save_row(db, row, profile)
    return _payload(row, profile, db)


@router.post("/{student_id}/eligibility/writeback")
def eligibility_writeback(
    student_id: int,
    payload: StudentEligibilityWriteback,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.kind not in ("international", "huaqiao"):
        raise HTTPException(status_code=400, detail="判定类型无效")
    row = _owned(db, user, student_id)
    profile = apply_eligibility_result(
        _decrypt_row(row),
        payload.kind,
        {
            "result": payload.result,
            "conclusion": payload.conclusion or payload.explanation,
            "explanation": payload.explanation,
            "record_id": payload.record_id,
            "policy_version": payload.policy_version,
        },
        confirm=payload.confirm,
    )
    _save_row(db, row, profile)
    return _payload(row, profile, db)


@router.get("/{student_id}/portrait")
def get_portrait(student_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = _owned(db, user, student_id)
    profile = _decrypt_row(row)
    items = _timeline_items_for(db, row.id, user.id)
    portrait = portrait_service.generate(profile, timeline_summary(items))
    return {"student_id": row.id, "portrait": portrait, "profile_updated_at": profile.get("updated_at")}


@router.get("/{student_id}/timeline")
def get_timeline(student_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = _owned(db, user, student_id)
    items = _timeline_items_for(db, row.id, user.id)
    return {
        "student_id": row.id,
        "items": items,
        "groups": group_timeline(items),
        "summary": timeline_summary(items),
    }


@router.post("/{student_id}/timeline/regenerate")
def regenerate_timeline(student_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = _owned(db, user, student_id)
    profile = _decrypt_row(row)
    regen = regenerate_student_timeline(db, row.id, user.id, user.tenant_id, profile)
    items = _timeline_items_for(db, row.id, user.id)
    return {
        "student_id": row.id,
        "items": items,
        "groups": group_timeline(items),
        "summary": timeline_summary(items),
        "portrait": portrait_service.generate(profile, timeline_summary(items)),
        "unresolved_targets": regen.get("unresolved_targets") or [],
        "matched_source_count": regen.get("matched_source_count") or 0,
    }


def _parse_optional_date(value: str | None):
    text = (value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"日期格式无效: {value}") from exc


@router.post("/{student_id}/timeline/manual")
def create_manual_timeline(
    student_id: int,
    payload: StudentTimelineManualCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _owned(db, user, student_id)
    item = StudentTimelineItem(
        student_id=row.id,
        user_id=user.id,
        tenant_id=user.tenant_id,
        title=payload.title,
        description=payload.description or "",
        start_date=_parse_optional_date(payload.start_date),
        deadline=_parse_optional_date(payload.deadline),
        university_name=payload.university_name or "",
        entry_year=payload.entry_year,
        application_route=payload.application_route or "",
        student_note=payload.student_note or "",
        is_manual=True,
        status="NOT_STARTED",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    item.status = compute_status(item)
    db.add(item)
    db.commit()
    db.refresh(item)
    return serialize_item(item)


@router.patch("/{student_id}/timeline/{item_id}")
def patch_timeline_item(
    student_id: int,
    item_id: int,
    payload: StudentTimelinePatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _owned(db, user, student_id)
    item = (
        db.query(StudentTimelineItem)
        .filter(
            StudentTimelineItem.id == item_id,
            StudentTimelineItem.student_id == student_id,
            StudentTimelineItem.user_id == user.id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="时间轴事项不存在")
    if payload.status is not None:
        if payload.status not in TIMELINE_STATUSES:
            raise HTTPException(status_code=400, detail="无效状态")
        item.status = payload.status
        if payload.status == "COMPLETED":
            item.completed_at = datetime.utcnow()
        elif payload.status in ("NOT_STARTED", "IN_PROGRESS", "NOT_APPLICABLE"):
            if payload.status != "COMPLETED":
                pass
    if payload.student_note is not None:
        item.student_note = payload.student_note
    if payload.title is not None and item.is_manual:
        item.title = payload.title
    if payload.description is not None and item.is_manual:
        item.description = payload.description
    if payload.deadline is not None:
        item.deadline = _parse_optional_date(payload.deadline)
    if payload.start_date is not None:
        item.start_date = _parse_optional_date(payload.start_date)
    if payload.university_name is not None:
        item.university_name = payload.university_name
    if payload.application_route is not None:
        item.application_route = payload.application_route
    if item.status not in ("COMPLETED", "NOT_APPLICABLE", "IN_PROGRESS"):
        item.status = compute_status(item)
    item.updated_at = datetime.utcnow()
    db.add(item)
    db.commit()
    db.refresh(item)
    return serialize_item(item)


@router.get("/{student_id}/timeline-matches")
def timeline_matches(
    student_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Read-only match against existing admission schedules. Does not mutate timeline rows."""
    row = _owned(db, user, student_id)
    profile = _decrypt_row(row)
    names = [t.get("university_name") for t in profile["goals"]["targets"] if t.get("university_name")]
    years = {str(t.get("entry_year")) for t in profile["goals"]["targets"] if t.get("entry_year")}
    if not names:
        return {"matches": []}
    universities = db.query(University).filter(University.name.in_(names)).all()
    by_id = {u.id: u for u in universities}
    if not by_id:
        return {"matches": []}
    q = db.query(AdmissionSchedule).filter(AdmissionSchedule.university_id.in_(list(by_id.keys())))
    items = []
    for s in q.order_by(AdmissionSchedule.year, AdmissionSchedule.month).all():
        uni = by_id.get(s.university_id)
        if years and str(s.year) not in years and str(s.year) not in {y[:4] for y in years}:
            continue
        items.append(
            {
                "id": s.id,
                "university_name": uni.name if uni else "",
                "year": s.year,
                "month": s.month,
                "registration_time": s.registration_time,
                "material_deadline": s.material_deadline,
                "exam_time": s.exam_time,
                "reminder": s.reminder,
            }
        )
    return {"matches": items}
