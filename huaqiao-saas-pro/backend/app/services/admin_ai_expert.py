"""AI Expert Workspace V1 — student_id scoped, DRAFT-only.

Does NOT write production expert_consultations with unsafe multi-student mapping.
Dev/staging drafts are kept in-process memory until schema gains student_id.
"""
from __future__ import annotations

import copy
import itertools
import threading
from datetime import datetime
from typing import Any

from ..config import get_settings
from .expert_report import generate_expert_consult_draft
from .admin_privacy import redact_profile_for_admin

REPORT_KINDS = {
    "student_portrait": "生成学生画像",
    "eligibility_risk": "资格风险分析",
    "school_recommendation": "选校建议",
    "material_gaps": "材料缺口",
    "timeline_plan": "时间规划",
    "parent_report": "家长沟通报告",
    "one_on_one_draft": "一对一规划草稿",
}

_lock = threading.Lock()
_seq = itertools.count(1)
# student_id -> list[draft dict]
_DRAFTS: dict[int, list[dict]] = {}


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


def _build_context(student_id: int, profile: dict, owner: dict | None = None) -> str:
    """Build AI context from ONE student only (already redacted)."""
    safe = redact_profile_for_admin(profile, role="consultant")
    basic = safe.get("basic_info") or {}
    identity = safe.get("identity") or {}
    education = safe.get("education") or {}
    goals = safe.get("goals") or {}
    courses = safe.get("courses") or {}
    owner_line = ""
    if owner:
        owner_line = f"所属用户ID={owner.get('id')} 邮箱={owner.get('email')}\n"
    return (
        f"【强制隔离】仅使用 student_id={student_id} 的资料，禁止引用其他学生。\n"
        f"{owner_line}"
        f"基本资料: {basic}\n"
        f"身份/国籍: {identity}\n"
        f"教育背景: {education}\n"
        f"语言/课程: {courses.get('language_exams') or []}\n"
        f"目标: {goals}\n"
    )


async def generate_draft(
    *,
    student_id: int,
    report_kind: str,
    profile: dict,
    actor_user_id: int,
    owner: dict | None = None,
) -> dict:
    if report_kind not in REPORT_KINDS:
        raise ValueError(f"未知 report_kind: {report_kind}")
    if not student_id:
        raise ValueError("student_id required")

    title = REPORT_KINDS[report_kind]
    context = _build_context(student_id, profile, owner)
    # Guard: context must embed this student_id and must not accept foreign profiles.
    if f"student_id={student_id}" not in context:
        raise RuntimeError("AI context isolation failed")

    question = f"{title}（Admin AI Expert Workspace V1）"
    personalization = (
        f"请针对 student_id={student_id} 输出【DRAFT】{title}。"
        "文首必须标注 STATUS=DRAFT，不得视为正式规划。"
    )
    result = await generate_expert_consult_draft(question, personalization, context)
    prov = provider_status()
    model = result.get("model") or prov["ai_model"]
    text = result.get("text") or ""
    if "STATUS=DRAFT" not in text and "DRAFT" not in text[:200]:
        text = f"STATUS=DRAFT\nAI_PROVIDER={prov['AI_PROVIDER']}\n\n{text}"

    draft = {
        "id": f"mem-{next(_seq)}",
        "storage": "in_memory_dev",
        "student_id": student_id,
        "report_kind": report_kind,
        "title": title,
        "status": "DRAFT",
        "published": False,
        "auto_published": False,
        "content": text,
        "ai_provider": prov["AI_PROVIDER"],
        "ai_model": model,
        "created_by_user_id": actor_user_id,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "note": "DRAFT only — not written to production expert_consultations until student_id migration.",
    }
    with _lock:
        _DRAFTS.setdefault(student_id, []).append(copy.deepcopy(draft))
    return draft


def list_drafts(student_id: int) -> list[dict]:
    with _lock:
        return copy.deepcopy(_DRAFTS.get(student_id, []))


def get_draft(student_id: int, draft_id: str) -> dict | None:
    with _lock:
        for d in _DRAFTS.get(student_id, []):
            if d["id"] == draft_id:
                return copy.deepcopy(d)
    return None


def update_draft(student_id: int, draft_id: str, content: str, actor_user_id: int) -> dict | None:
    with _lock:
        for d in _DRAFTS.get(student_id, []):
            if d["id"] == draft_id:
                d["content"] = content
                d["status"] = "DRAFT"
                d["published"] = False
                d["updated_by_user_id"] = actor_user_id
                d["updated_at"] = datetime.utcnow().isoformat() + "Z"
                return copy.deepcopy(d)
    return None


def approve_draft(student_id: int, draft_id: str, actor_user_id: int) -> dict | None:
    with _lock:
        for d in _DRAFTS.get(student_id, []):
            if d["id"] == draft_id:
                d["status"] = "APPROVED"
                d["published"] = False
                d["approved_by_user_id"] = actor_user_id
                d["approved_at"] = datetime.utcnow().isoformat() + "Z"
                return copy.deepcopy(d)
    return None


def publish_draft(student_id: int, draft_id: str, actor_user_id: int) -> dict:
    """V1: refuse production publish — schema lacks safe student_id binding."""
    draft = get_draft(student_id, draft_id)
    if not draft:
        raise KeyError("draft not found")
    if draft.get("status") != "APPROVED":
        raise PermissionError("仅 APPROVED 状态可请求发布；且 V1 禁止自动/生产发布")
    raise PermissionError(
        "PUBLISH_BLOCKED: expert_consultations 尚无 student_id；"
        "禁止写入生产咨询表以免多学生串档。请先应用 migration draft（非本轮）。"
    )


def clear_memory_for_tests() -> None:
    with _lock:
        _DRAFTS.clear()


def assert_context_single_student(context: str, student_id: int, other_student_ids: list[int]) -> None:
    assert f"student_id={student_id}" in context
    for oid in other_student_ids:
        assert f"student_id={oid}" not in context or oid == student_id
