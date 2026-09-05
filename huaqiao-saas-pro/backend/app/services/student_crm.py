"""Student CRM V1 — assignee, stages, follow-ups, list enrichment.

Never stores or returns cipher_blob / raw passport / national ID.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from ..models import ExpertConsultation, StudentFollowUp, StudentMasterProfile, User
from . import admin_audit
from .student_profile import display_name_of, normalize_profile, profile_summary

CRM_STAGES = (
    "UNASSIGNED",
    "NEW",
    "CONTACTED",
    "PLANNING",
    "WAITING_STUDENT",
    "WAITING_DOCUMENTS",
    "APPLICATION",
    "FOLLOW_UP",
    "COMPLETED",
    "PAUSED",
)

CRM_STAGE_LABELS_ZH = {
    "UNASSIGNED": "未分配",
    "NEW": "新学生",
    "CONTACTED": "已联系",
    "PLANNING": "规划中",
    "WAITING_STUDENT": "等待学生",
    "WAITING_DOCUMENTS": "等待材料",
    "APPLICATION": "申请中",
    "FOLLOW_UP": "持续跟进",
    "COMPLETED": "已完成",
    "PAUSED": "暂停",
}

RISK_LEVELS = ("NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL")
FOLLOW_UP_SOURCES = ("HUMAN", "AI_ASSISTED", "SYSTEM")
STAFF_ROLES = frozenset({"admin", "consultant", "support", "super_admin", "operations_admin"})
ASSIGNABLE_ROLES = frozenset({"admin", "consultant", "super_admin", "operations_admin"})
PLACEHOLDER_NAMES = frozenset({"", "未命名学生", "未命名学生", "待补姓名"})

STUDENT_ASSIGNED = "STUDENT_ASSIGNED"
STUDENT_REASSIGNED = "STUDENT_REASSIGNED"
STUDENT_FOLLOW_UP_CREATE = "STUDENT_FOLLOW_UP_CREATE"
STUDENT_CRM_UPDATE = "STUDENT_CRM_UPDATE"
STUDENT_NAME_REPAIR = "STUDENT_NAME_REPAIR"


def stage_label(stage: str | None) -> str:
    return CRM_STAGE_LABELS_ZH.get((stage or "UNASSIGNED").upper(), stage or "未分配")


def is_placeholder_name(name: str | None) -> bool:
    return (name or "").strip() in PLACEHOLDER_NAMES


def admin_display_name(row: StudentMasterProfile, profile: dict | None = None) -> str:
    """Prefer DB display_name; refresh from cipher names when available; never invent."""
    dn = (row.display_name or "").strip()
    if not is_placeholder_name(dn):
        return dn
    if profile:
        resolved = display_name_of(profile)
        if not is_placeholder_name(resolved):
            return resolved
    return "待补姓名"


def sync_display_name_from_profile(row: StudentMasterProfile, profile: dict) -> str:
    name = display_name_of(profile)
    row.display_name = name
    return name


def staff_label(user: User | None) -> str:
    if not user:
        return "未分配"
    name = (user.name or "").strip()
    role = (user.role or "").lower()
    if name:
        return name
    if role == "admin":
        return "管理员Admin"
    return user.email or f"用户#{user.id}"


def list_staff_candidates(db: Session) -> list[dict]:
    rows = (
        db.query(User)
        .filter(User.role.in_(list(STAFF_ROLES)))
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
            "label": staff_label(u),
        }
        for u in rows
    ]


def serialize_follow_up(row: StudentFollowUp, operator: User | None = None) -> dict:
    return {
        "id": row.id,
        "student_id": row.student_id,
        "operator_user_id": row.operator_user_id,
        "operator_label": staff_label(operator) if operator else None,
        "operator_type": row.operator_type,
        "source": row.source,
        "type": row.type,
        "content": row.content or "",
        "summary": row.summary or "",
        "next_action": row.next_action,
        "next_follow_up_at": row.next_follow_up_at.isoformat() if row.next_follow_up_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def crm_snapshot(db: Session, row: StudentMasterProfile, profile: dict | None = None) -> dict:
    assignee = None
    if row.assignee_user_id:
        assignee = db.query(User).filter(User.id == row.assignee_user_id).first()
    summary = profile_summary(normalize_profile(profile or {})) if profile is not None else {}
    targets = summary.get("target_universities") or []
    display = admin_display_name(row, profile)
    stage = row.crm_stage or "UNASSIGNED"
    return {
        "assignee_user_id": row.assignee_user_id,
        "assignee_label": staff_label(assignee),
        "assigned_at": row.assigned_at.isoformat() if row.assigned_at else None,
        "assigned_by_user_id": row.assigned_by_user_id,
        "crm_stage": stage,
        "crm_stage_label": stage_label(stage),
        "risk_level": row.risk_level or "NONE",
        "next_action": row.next_action or "",
        "next_follow_up_at": row.next_follow_up_at.isoformat() if row.next_follow_up_at else None,
        "last_follow_up_at": row.last_follow_up_at.isoformat() if row.last_follow_up_at else None,
        "identity_track": row.identity_track or "",
        "display_name": display,
        "display_name_needs_repair": is_placeholder_name(row.display_name),
        "target_universities": [t for t in targets if t][:5],
        "intended_entry_year": summary.get("intended_entry_year") or "",
        "international_status": summary.get("international_status") or "",
        "huaqiao_status": summary.get("huaqiao_status") or "",
    }


def assign_student(
    db: Session,
    *,
    row: StudentMasterProfile,
    assignee_user_id: int | None,
    operator: User,
) -> dict:
    prev = row.assignee_user_id
    if assignee_user_id is not None:
        staff = db.query(User).filter(User.id == assignee_user_id).first()
        if not staff or not staff.is_active or (staff.role or "").lower() not in ASSIGNABLE_ROLES:
            raise ValueError("assignee must be an active consultant/admin")
        row.assignee_user_id = assignee_user_id
        row.assigned_at = datetime.utcnow()
        row.assigned_by_user_id = operator.id
        if (row.crm_stage or "UNASSIGNED") == "UNASSIGNED":
            row.crm_stage = "NEW"
        action = STUDENT_REASSIGNED if prev and prev != assignee_user_id else STUDENT_ASSIGNED
    else:
        row.assignee_user_id = None
        row.assigned_at = None
        row.assigned_by_user_id = operator.id
        if (row.crm_stage or "") == "NEW":
            row.crm_stage = "UNASSIGNED"
        action = STUDENT_REASSIGNED if prev else STUDENT_ASSIGNED

    row.updated_at = datetime.utcnow()
    db.add(row)
    db.commit()
    db.refresh(row)

    admin_audit.record_audit(
        db,
        actor_user_id=operator.id,
        action=action,
        resource_type="student_master_profile",
        resource_id=row.id,
        student_id=row.id,
        metadata={"from_user": prev, "to_user": row.assignee_user_id, "operator": operator.id},
    )
    admin_audit.record_audit(
        db,
        actor_user_id=operator.id,
        action="STUDENT_ASSIGNMENT_CHANGE",
        resource_type="student_master_profile",
        resource_id=row.id,
        student_id=row.id,
        metadata={"from_user": prev, "to_user": row.assignee_user_id, "operator": operator.id},
    )
    return crm_snapshot(db, row)


def create_follow_up(
    db: Session,
    *,
    row: StudentMasterProfile,
    operator: User,
    content: str,
    summary: str = "",
    type_: str = "NOTE",
    source: str = "HUMAN",
    next_action: str | None = None,
    next_follow_up_at: datetime | None = None,
) -> dict:
    src = (source or "HUMAN").upper()
    if src not in FOLLOW_UP_SOURCES:
        raise ValueError("invalid follow-up source")
    if src == "HUMAN" and str(type_ or "").upper().startswith("AI_"):
        src = "AI_ASSISTED"

    fu = StudentFollowUp(
        student_id=row.id,
        operator_user_id=operator.id,
        operator_type="ADMIN" if (operator.role or "").lower() in ("admin", "super_admin") else "STAFF",
        source=src,
        type=(type_ or "NOTE").upper(),
        content=(content or "").strip(),
        summary=(summary or "").strip()[:240],
        next_action=next_action,
        next_follow_up_at=next_follow_up_at,
        created_at=datetime.utcnow(),
    )
    db.add(fu)
    row.last_follow_up_at = fu.created_at
    if next_action is not None:
        row.next_action = next_action
    if next_follow_up_at is not None:
        row.next_follow_up_at = next_follow_up_at
    if (row.crm_stage or "UNASSIGNED") in ("UNASSIGNED", "NEW"):
        row.crm_stage = "CONTACTED"
    row.updated_at = datetime.utcnow()
    db.add(row)
    db.commit()
    db.refresh(fu)

    admin_audit.record_audit(
        db,
        actor_user_id=operator.id,
        action=STUDENT_FOLLOW_UP_CREATE,
        resource_type="student_follow_up",
        resource_id=fu.id,
        student_id=row.id,
        metadata={"source": src, "type": fu.type},
    )
    admin_audit.record_audit(
        db,
        actor_user_id=operator.id,
        action="FOLLOW_UP_CREATE",
        resource_type="student_follow_up",
        resource_id=fu.id,
        student_id=row.id,
        metadata={"source": src, "type": fu.type},
    )
    return serialize_follow_up(fu, operator)


def list_follow_ups(db: Session, student_id: int, limit: int = 50) -> list[dict]:
    rows = (
        db.query(StudentFollowUp)
        .filter(StudentFollowUp.student_id == student_id)
        .order_by(StudentFollowUp.created_at.desc())
        .limit(limit)
        .all()
    )
    ops: dict[int, User | None] = {}
    for r in rows:
        if r.operator_user_id and r.operator_user_id not in ops:
            ops[r.operator_user_id] = db.query(User).filter(User.id == r.operator_user_id).first()
    return [serialize_follow_up(r, ops.get(r.operator_user_id)) for r in rows]


def patch_crm_fields(
    db: Session,
    *,
    row: StudentMasterProfile,
    operator: User,
    crm_stage: str | None = None,
    risk_level: str | None = None,
    next_action: str | None = None,
    next_follow_up_at: Any = ...,
    identity_track: str | None = None,
    display_name_override: str | None = None,
) -> dict:
    prev_stage = row.crm_stage
    if crm_stage is not None:
        stage = crm_stage.upper()
        if stage not in CRM_STAGES:
            raise ValueError("invalid crm_stage")
        row.crm_stage = stage
    if risk_level is not None:
        risk = risk_level.upper()
        if risk not in RISK_LEVELS:
            raise ValueError("invalid risk_level")
        row.risk_level = risk
    if next_action is not None:
        row.next_action = next_action
    if next_follow_up_at is not ...:
        if next_follow_up_at is None or next_follow_up_at == "":
            row.next_follow_up_at = None
        elif isinstance(next_follow_up_at, datetime):
            row.next_follow_up_at = next_follow_up_at
        else:
            row.next_follow_up_at = datetime.fromisoformat(str(next_follow_up_at).replace("Z", ""))
    if identity_track is not None:
        row.identity_track = identity_track[:40]
    if display_name_override is not None:
        name = display_name_override.strip()
        if not name:
            raise ValueError("display_name cannot be empty")
        if "@" in name:
            raise ValueError("email must not be used as student display_name")
        row.display_name = name[:160]
        admin_audit.record_audit(
            db,
            actor_user_id=operator.id,
            action=STUDENT_NAME_REPAIR,
            resource_type="student_master_profile",
            resource_id=row.id,
            student_id=row.id,
            metadata={"display_name_set": True},
        )

    row.updated_at = datetime.utcnow()
    db.add(row)
    db.commit()
    db.refresh(row)
    admin_audit.record_audit(
        db,
        actor_user_id=operator.id,
        action=STUDENT_CRM_UPDATE,
        resource_type="student_master_profile",
        resource_id=row.id,
        student_id=row.id,
        metadata={"crm_stage": row.crm_stage, "risk_level": row.risk_level},
    )
    if crm_stage is not None and row.crm_stage != prev_stage:
        admin_audit.record_audit(
            db,
            actor_user_id=operator.id,
            action="CRM_STAGE_CHANGE",
            resource_type="student_master_profile",
            resource_id=row.id,
            student_id=row.id,
            metadata={"from_stage": prev_stage, "to_stage": row.crm_stage},
        )
    return crm_snapshot(db, row)


def dashboard_crm_todos(db: Session, *, assignee_user_id: int | None = None) -> dict[str, Any]:
    now = datetime.utcnow()
    base = db.query(StudentMasterProfile).filter(StudentMasterProfile.status != "DELETED")
    if assignee_user_id:
        base = base.filter(StudentMasterProfile.assignee_user_id == assignee_user_id)

    def _ids(q) -> list[int]:
        return [r.id for r in q.limit(100).all()]

    unassigned = base.filter(StudentMasterProfile.assignee_user_id.is_(None))
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = now.replace(hour=23, minute=59, second=59, microsecond=0)
    due_today = base.filter(
        StudentMasterProfile.next_follow_up_at.isnot(None),
        StudentMasterProfile.next_follow_up_at <= end,
        StudentMasterProfile.next_follow_up_at >= start,
    )
    overdue = base.filter(
        StudentMasterProfile.next_follow_up_at.isnot(None),
        StudentMasterProfile.next_follow_up_at < start,
    )
    high_risk = base.filter(StudentMasterProfile.risk_level.in_(["HIGH", "CRITICAL"]))
    waiting_docs = base.filter(StudentMasterProfile.crm_stage == "WAITING_DOCUMENTS")

    ai_pending = (
        db.query(ExpertConsultation)
        .filter(
            ExpertConsultation.status.in_(
                ["DRAFT", "REVIEWED", "APPROVED", "draft_ready", "pending_review", "pending_ai"]
            )
        )
        .limit(100)
        .all()
    )

    return {
        "unassigned_students": _ids(unassigned),
        "due_today": _ids(due_today),
        "overdue_follow_ups": _ids(overdue),
        "high_risk_students": _ids(high_risk),
        "waiting_documents": _ids(waiting_docs),
        "ai_pending_review": [
            {
                "id": c.id,
                "student_id": c.student_id,
                "status": c.status,
                "title": getattr(c, "title", "") or "",
            }
            for c in ai_pending
            if c.student_id
        ],
        "counts": {
            "unassigned": unassigned.count(),
            "due_today": due_today.count(),
            "overdue": overdue.count(),
            "high_risk": high_risk.count(),
            "waiting_documents": waiting_docs.count(),
            "ai_pending_review": len(ai_pending),
        },
    }


def ai_follow_up_drafts(*, student_id: int, crm: dict) -> list[dict]:
    """DRAFT-only AI follow-up suggestions. Never auto-send."""
    name = crm.get("display_name") or f"学生#{student_id}"
    stage = crm.get("crm_stage_label") or crm.get("crm_stage")
    nxt = crm.get("next_action") or "确认本周材料与时间节点"
    targets = "、".join(crm.get("target_universities") or []) or "目标院校待确认"
    return [
        {
            "action": "今日跟进建议",
            "source": "AI_ASSISTED",
            "status": "DRAFT",
            "content": f"跟进 {name}（阶段：{stage}）。重点：{nxt}。目标方向：{targets}。",
            "auto_send": False,
        },
        {
            "action": "家长沟通摘要",
            "source": "AI_ASSISTED",
            "status": "DRAFT",
            "content": f"{name} 当前阶段为「{stage}」。建议向家长同步：下一步「{nxt}」，并确认材料齐全度。",
            "auto_send": False,
        },
        {
            "action": "学生下一步计划",
            "source": "AI_ASSISTED",
            "status": "DRAFT",
            "content": f"1) 完成「{nxt}」；2) 核对入学年份与选校清单；3) 更新 CSCA/语言成绩进度。",
            "auto_send": False,
        },
        {
            "action": "材料缺口",
            "source": "AI_ASSISTED",
            "status": "DRAFT",
            "content": "请核对：成绩单、语言成绩、护照/身份材料、推荐信、个人陈述是否齐全（仅提示，不编造缺失项）。",
            "auto_send": False,
        },
        {
            "action": "时间线风险",
            "source": "AI_ASSISTED",
            "status": "DRAFT",
            "content": "检查即将到期与逾期时间线节点；无真实日期时保持「待官方公布」，禁止编造。",
            "auto_send": False,
        },
        {
            "action": "最近跟进总结",
            "source": "AI_ASSISTED",
            "status": "DRAFT",
            "content": (
                f"负责人：{crm.get('assignee_label')}；阶段：{stage}；"
                f"下一步：{nxt}；下次跟进：{crm.get('next_follow_up_at') or '未设置'}。"
            ),
            "auto_send": False,
        },
    ]


def enrich_ai_context_block(crm: dict, follow_up_summary: str = "") -> str:
    return (
        f"CRM负责人: {crm.get('assignee_label')}\n"
        f"CRM阶段: {crm.get('crm_stage')} ({crm.get('crm_stage_label')})\n"
        f"下一步: {crm.get('next_action') or '—'}\n"
        f"下次跟进: {crm.get('next_follow_up_at') or '—'}\n"
        f"风险: {crm.get('risk_level')}\n"
        f"跟进摘要: {follow_up_summary or '—'}\n"
    )
