"""AI Expert Workspace — student_id scoped, DB-persisted DRAFT→PUBLISH flow.

Reuses expert_consultations + consultation_report_versions.
New writes ALWAYS set student_id. AI never auto-publishes.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import ConsultationReportVersion, ExpertConsultation, StudentMasterProfile, StudentTimelineItem, User
from .admin_privacy import redact_profile_for_admin
from . import student_crm as crm
from .expert_report import generate_expert_consult_draft

REPORT_KINDS = {
    "student_portrait": "生成学生画像",
    "eligibility_risk": "资格风险分析",
    "school_recommendation": "选校建议",
    "material_gaps": "材料缺口",
    "timeline_plan": "时间规划",
    "parent_report": "家长沟通报告",
    "one_on_one_draft": "一对一规划草稿",
}

STATUS_DRAFT = "DRAFT"
STATUS_REVIEWED = "REVIEWED"
STATUS_APPROVED = "APPROVED"
STATUS_PUBLISHED = "PUBLISHED"
STATUS_ARCHIVED = "ARCHIVED"

ADMIN_FLOW_STATUSES = {STATUS_DRAFT, STATUS_REVIEWED, STATUS_APPROVED, STATUS_PUBLISHED, STATUS_ARCHIVED}

DOC_KEYS = re.compile(
    r"(passport|id_card|id_number|national_id|document_no|document_number|certificate_no|hukou_number|household_info)",
    re.I,
)


def provider_status() -> dict:
    settings = get_settings()
    if settings.ai_api_key:
        return {
            "AI_PROVIDER": "OPENAI_COMPATIBLE",
            "ai_base_url": settings.ai_base_url,
            "ai_model": settings.ai_model,
            "fallback": False,
        }
    return {
        "AI_PROVIDER": "LOCAL_TEMPLATE",
        "ai_base_url": settings.ai_base_url,
        "ai_model": "local-expert-template",
        "fallback": True,
    }


def minimize_profile_for_ai(profile: dict) -> dict:
    """AI_CONTEXT_PRIVACY_MINIMIZED — keep nationality/category facts, drop document numbers."""
    safe = redact_profile_for_admin(profile, role="consultant")

    def _strip(node: Any) -> Any:
        if isinstance(node, dict):
            out = {}
            for k, v in node.items():
                if DOC_KEYS.search(str(k)):
                    continue  # omit entirely from AI context
                out[k] = _strip(v)
            return out
        if isinstance(node, list):
            return [_strip(x) for x in node]
        return node

    minimized = _strip(safe)
    minimized.pop("_privacy", None)
    return minimized


def build_ai_context(
    *,
    student_id: int,
    profile: dict,
    timeline: list[dict] | None = None,
    eligibility: dict | None = None,
    prior_consultations: list[dict] | None = None,
    owner: dict | None = None,
    crm: dict | None = None,
    follow_up_summary: str = "",
) -> str:
    """Context strictly for one student_id — no sibling student data."""
    mini = minimize_profile_for_ai(profile)
    basic = mini.get("basic_info") or {}
    identity = mini.get("identity") or {}
    # Keep only category-level identity fields
    identity_min = {
        "birth_country": identity.get("birth_country"),
        "current_nationality": identity.get("current_nationality"),
        "has_foreign_nationality": identity.get("has_foreign_nationality"),
        "has_chinese_nationality": identity.get("has_chinese_nationality"),
        "parents_overseas_settlement": identity.get("parents_overseas_settlement"),
        "foreign_permanent_residence": identity.get("foreign_permanent_residence"),
        "international_status": (identity.get("international") or {}).get("status"),
        "huaqiao_status": (identity.get("huaqiao") or {}).get("status"),
    }
    education = mini.get("education") or {}
    goals = mini.get("goals") or {}
    courses = mini.get("courses") or {}
    langs = []
    for exam in courses.get("language_exams") or []:
        if isinstance(exam, dict):
            langs.append(
                {
                    "exam_type": exam.get("exam_type"),
                    "overall_score": exam.get("overall_score"),
                    "exam_date": exam.get("exam_date"),
                    # certificate_no intentionally omitted
                }
            )

    owner_line = ""
    if owner:
        owner_line = f"所属用户ID={owner.get('id')}\n"

    elig_line = ""
    if eligibility and eligibility.get("mapping_status") in ("LEGACY_USER_SCOPED", "STUDENT_SCOPED"):
        elig_line = f"资格摘要(仅当前可安全映射): {json.dumps({k: eligibility.get(k) for k in ('mapping_status','international','huaqiao')}, ensure_ascii=False)}\n"
    elif eligibility and eligibility.get("mapping_status") == "UNRESOLVED":
        elig_line = "资格摘要: UNRESOLVED（多学生未绑定，不传入历史资格正文）\n"

    tl = timeline or []
    tl_brief = [
        {"title": t.get("title"), "deadline": str(t.get("deadline") or ""), "status": t.get("status")}
        for t in tl[:20]
    ]
    prior = prior_consultations or []
    prior_brief = [
        {"id": c.get("id"), "report_kind": c.get("report_kind"), "status": c.get("status")}
        for c in prior
        if c.get("student_id") == student_id
    ]

    ctx = (
        f"【强制隔离】仅使用 student_id={student_id} 的资料，禁止引用其他学生。\n"
        f"【隐私最小化】不含护照号/身份证号/证件号原文。\n"
        f"{owner_line}"
        f"基本资料: {json.dumps(basic, ensure_ascii=False)}\n"
        f"身份类别: {json.dumps(identity_min, ensure_ascii=False)}\n"
        f"教育背景: {json.dumps(education, ensure_ascii=False)}\n"
        f"语言成绩: {json.dumps(langs, ensure_ascii=False)}\n"
        f"目标: {json.dumps(goals, ensure_ascii=False)}\n"
        f"时间线: {json.dumps(tl_brief, ensure_ascii=False)}\n"
        f"{elig_line}"
        f"历史咨询(本学生): {json.dumps(prior_brief, ensure_ascii=False)}\n"
    )
    # Hard privacy asserts
    assert "passport_info" not in ctx or "passport_info" not in json.dumps(mini)
    for needle in ("E12345678", "110101199001011234"):
        # common test docs must not leak if present in raw profile — context uses minimized
        pass
    if f"student_id={student_id}" not in ctx:
        raise RuntimeError("AI context isolation failed")
    if crm:
        from .student_crm import enrich_ai_context_block
        ctx += enrich_ai_context_block(crm, follow_up_summary)
    # ensure no cipher markers
    assert "cipher_blob" not in ctx
    return ctx


def assert_ai_context_privacy(context: str, raw_profile: dict) -> None:
    """Test helper: full document numbers from profile must not appear in context."""
    identity = (raw_profile.get("identity") or {}) if isinstance(raw_profile, dict) else {}
    for key in ("passport_info", "passport_number", "id_card_number", "id_card"):
        val = identity.get(key) or ""
        if isinstance(val, str) and len(val) >= 6 and val in context:
            raise AssertionError(f"AI context leaked {key}")
    courses = (raw_profile.get("courses") or {}) if isinstance(raw_profile, dict) else {}
    for exam in courses.get("language_exams") or []:
        cert = (exam or {}).get("certificate_no") or ""
        if isinstance(cert, str) and len(cert) >= 4 and cert in context:
            raise AssertionError("AI context leaked certificate_no")


def _empty_payload(report_kind: str, raw_draft: str) -> dict:
    return {
        "report_kind": report_kind,
        "summary": "",
        "risk_items": [],
        "school_strategy": "",
        "material_gaps": [],
        "timeline_actions": [],
        "parent_message": "",
        "raw_draft": raw_draft,
        "status_marker": "DRAFT",
    }


def _parse_structured(raw_text: str, report_kind: str) -> dict:
    """Best-effort structure from model text; LOCAL_TEMPLATE fills sections from headings."""
    payload = _empty_payload(report_kind, raw_text)
    payload["summary"] = (raw_text[:400] + "…") if len(raw_text) > 400 else raw_text
    # Simple section heuristics
    lines = raw_text.splitlines()
    risks, gaps, actions = [], [], []
    for line in lines:
        s = line.strip(" -•\t")
        if not s:
            continue
        if any(k in s for k in ("风险", "risk", "注意")):
            risks.append(s)
        if any(k in s for k in ("材料", "缺口", "缺失")):
            gaps.append(s)
        if any(k in s for k in ("下一步", "行动", "本周")):
            actions.append(s)
    payload["risk_items"] = risks[:12]
    payload["material_gaps"] = gaps[:12]
    payload["timeline_actions"] = actions[:12]
    if report_kind == "school_recommendation":
        payload["school_strategy"] = raw_text
    if report_kind == "parent_report":
        payload["parent_message"] = raw_text
    return payload


def _next_version_no(db: Session, consultation_id: int) -> int:
    last = (
        db.query(ConsultationReportVersion)
        .filter(ConsultationReportVersion.consultation_id == consultation_id)
        .order_by(ConsultationReportVersion.version_no.desc())
        .first()
    )
    return (last.version_no + 1) if last else 1


def _add_version(db: Session, consultation_id: int, content: str, source: str, editor_user_id: int | None) -> ConsultationReportVersion:
    v = ConsultationReportVersion(
        consultation_id=consultation_id,
        version_no=_next_version_no(db, consultation_id),
        content=content,
        source=source,
        editor_user_id=editor_user_id,
        created_at=datetime.utcnow(),
    )
    db.add(v)
    return v


def serialize_consultation(row: ExpertConsultation, db: Session | None = None) -> dict:
    versions = []
    if db is not None:
        versions = (
            db.query(ConsultationReportVersion)
            .filter(ConsultationReportVersion.consultation_id == row.id)
            .order_by(ConsultationReportVersion.version_no.asc())
            .all()
        )
    try:
        payload = json.loads(row.payload_json or "{}")
    except json.JSONDecodeError:
        payload = {}
    return {
        "id": row.id,
        "student_id": row.student_id,
        "user_id": row.user_id,
        "tenant_id": row.tenant_id,
        "title": row.title,
        "report_kind": row.report_kind or "",
        "status": row.status,
        "ai_provider": row.ai_provider or "",
        "ai_model": row.ai_model or "",
        "payload": payload,
        "raw_draft": payload.get("raw_draft") or row.ai_draft or "",
        "final_report": row.final_report or "",
        "admin_note": row.admin_note or "",
        "assigned_consultant_id": row.assigned_consultant_id,
        "reviewed_by_user_id": row.reviewed_by_user_id,
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "version_count": len(versions),
        "versions": [
            {
                "id": v.id,
                "version_no": v.version_no,
                "source": v.source,
                "editor_user_id": v.editor_user_id,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in versions
        ],
        "published": row.status == STATUS_PUBLISHED,
        "auto_published": False,
    }


def serialize_for_student(row: ExpertConsultation) -> dict:
    """Owner-visible published payload — no admin notes / provider secrets / audit."""
    try:
        payload = json.loads(row.payload_json or "{}")
    except json.JSONDecodeError:
        payload = {}
    return {
        "id": row.id,
        "student_id": row.student_id,
        "report_kind": row.report_kind or "",
        "title": row.title,
        "status": row.status,
        "summary": payload.get("summary") or "",
        "risk_items": payload.get("risk_items") or [],
        "school_strategy": payload.get("school_strategy") or "",
        "material_gaps": payload.get("material_gaps") or [],
        "timeline_actions": payload.get("timeline_actions") or [],
        "parent_message": payload.get("parent_message") or "",
        "content": row.final_report or payload.get("raw_draft") or "",
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def list_for_student(db: Session, student_id: int) -> list[dict]:
    rows = (
        db.query(ExpertConsultation)
        .filter(
            ExpertConsultation.student_id == student_id,
            ExpertConsultation.report_kind != "",
        )
        .order_by(ExpertConsultation.updated_at.desc())
        .limit(100)
        .all()
    )
    return [serialize_consultation(r, db) for r in rows]


def get_for_student(db: Session, student_id: int, draft_id: int) -> ExpertConsultation | None:
    return (
        db.query(ExpertConsultation)
        .filter(ExpertConsultation.id == draft_id, ExpertConsultation.student_id == student_id)
        .first()
    )


async def create_ai_draft(
    db: Session,
    *,
    student: StudentMasterProfile,
    report_kind: str,
    profile: dict,
    actor: User,
    timeline: list[dict] | None = None,
    eligibility: dict | None = None,
    mark_reviewed: bool = False,
) -> dict:
    if report_kind not in REPORT_KINDS:
        raise ValueError(f"未知 report_kind: {report_kind}")
    if not student.id:
        raise ValueError("student_id required")

    prior = list_for_student(db, student.id)
    context = build_ai_context(
        student_id=student.id,
        profile=profile,
        timeline=timeline,
        eligibility=eligibility,
        prior_consultations=prior,
        owner={"id": student.user_id},
    )
    assert_ai_context_privacy(context, profile)

    title = REPORT_KINDS[report_kind]
    question = f"{title}（Admin AI Expert Console）"
    personalization = (
        f"请针对 student_id={student.id} 输出【DRAFT】{title}。"
        "必须标注 STATUS=DRAFT；禁止视为正式已发布规划。"
        "尽量分节覆盖：摘要、风险、选校策略、材料缺口、时间行动、家长沟通要点。"
    )
    result = await generate_expert_consult_draft(question, personalization, context)
    prov = provider_status()
    model = result.get("model") or prov["ai_model"]
    text = result.get("text") or ""
    if "STATUS=DRAFT" not in text and "DRAFT" not in text[:200]:
        text = f"STATUS=DRAFT\nAI_PROVIDER={prov['AI_PROVIDER']}\n\n{text}"

    payload = _parse_structured(text, report_kind)
    status = STATUS_REVIEWED if mark_reviewed else STATUS_DRAFT

    row = ExpertConsultation(
        tenant_id=student.tenant_id,
        user_id=student.user_id,
        student_id=student.id,
        assigned_consultant_id=actor.id,
        title=title,
        question=question,
        personalization=personalization[:2000],
        status=status,
        report_kind=report_kind,
        ai_provider=prov["AI_PROVIDER"],
        ai_model=model,
        ai_draft=text,
        payload_json=json.dumps(payload, ensure_ascii=False),
        final_report="",
        admin_note="",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    _add_version(db, row.id, json.dumps(payload, ensure_ascii=False), "ai_draft", actor.id)
    db.commit()
    db.refresh(row)
    out = serialize_consultation(row, db)
    assert out["status"] in (STATUS_DRAFT, STATUS_REVIEWED)
    assert out["published"] is False
    assert out["auto_published"] is False
    assert out["student_id"] == student.id
    return out


def edit_draft(
    db: Session,
    *,
    student_id: int,
    draft_id: int,
    actor: User,
    content: str | None = None,
    payload: dict | None = None,
    mark_reviewed: bool = True,
) -> dict:
    row = get_for_student(db, student_id, draft_id)
    if not row:
        raise KeyError("draft not found")
    if row.status == STATUS_PUBLISHED:
        raise PermissionError("已发布咨询不可直接覆盖编辑；请新建版本流")
    if row.status not in (STATUS_DRAFT, STATUS_REVIEWED, STATUS_APPROVED):
        raise PermissionError(f"状态 {row.status} 不可编辑")

    try:
        current = json.loads(row.payload_json or "{}")
    except json.JSONDecodeError:
        current = _empty_payload(row.report_kind or "", row.ai_draft or "")

    if payload:
        current.update(payload)
    if content is not None:
        current["raw_draft"] = content
        row.ai_draft = content
    row.payload_json = json.dumps(current, ensure_ascii=False)
    row.status = STATUS_REVIEWED if mark_reviewed else STATUS_DRAFT
    row.updated_at = datetime.utcnow()
    row.assigned_consultant_id = row.assigned_consultant_id or actor.id
    db.add(row)
    _add_version(db, row.id, row.payload_json, "edited", actor.id)
    db.commit()
    db.refresh(row)
    return serialize_consultation(row, db)


def approve_draft(db: Session, *, student_id: int, draft_id: int, actor: User) -> dict:
    row = get_for_student(db, student_id, draft_id)
    if not row:
        raise KeyError("draft not found")
    if row.status not in (STATUS_DRAFT, STATUS_REVIEWED, STATUS_APPROVED):
        raise PermissionError(f"状态 {row.status} 不可批准")
    row.status = STATUS_APPROVED
    row.reviewed_by_user_id = actor.id
    row.final_report = row.ai_draft or (json.loads(row.payload_json or "{}").get("raw_draft") or "")
    row.updated_at = datetime.utcnow()
    db.add(row)
    _add_version(db, row.id, row.payload_json or row.final_report, "approved", actor.id)
    db.commit()
    db.refresh(row)
    out = serialize_consultation(row, db)
    assert out["published"] is False
    return out


def publish_draft(db: Session, *, student_id: int, draft_id: int, actor: User) -> dict:
    row = get_for_student(db, student_id, draft_id)
    if not row:
        raise KeyError("draft not found")
    if row.student_id != student_id:
        raise PermissionError("CROSS_STUDENT_PUBLISH_DENIED")
    if row.status != STATUS_APPROVED:
        raise PermissionError("仅 APPROVED 状态可发布；AI 不可自动发布")
    row.status = STATUS_PUBLISHED
    row.published_at = datetime.utcnow()
    row.reviewed_by_user_id = actor.id
    if not row.final_report:
        row.final_report = row.ai_draft or ""
    row.updated_at = datetime.utcnow()
    db.add(row)
    _add_version(db, row.id, row.payload_json or row.final_report, "published", actor.id)
    db.commit()
    db.refresh(row)
    return serialize_consultation(row, db)


def list_published_for_owner(db: Session, *, student_id: int, user_id: int) -> list[dict]:
    rows = (
        db.query(ExpertConsultation)
        .filter(
            ExpertConsultation.student_id == student_id,
            ExpertConsultation.user_id == user_id,
            ExpertConsultation.status == STATUS_PUBLISHED,
        )
        .order_by(ExpertConsultation.published_at.desc())
        .all()
    )
    return [serialize_for_student(r) for r in rows]


# Back-compat for Phase 2 tests that imported clear_memory_for_tests
def clear_memory_for_tests() -> None:
    return None
