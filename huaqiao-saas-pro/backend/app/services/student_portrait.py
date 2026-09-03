"""Deterministic Student Portrait service.

Derived only from Student Master Profile facts.
Never invents university admission requirements or overrides eligibility engines.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .student_profile import (
    PRIORITY_LEVELS,
    age_from_birth_date,
    completeness,
    normalize_profile,
)

PORTRAIT_VERSION = "1.0.0"

# Soft grade bands for transparent, non-diagnostic summaries only.
_STRONG_MARKERS = {"A*", "A+", "A", "7", "6", "5", "Distinction", "满分", "优秀"}
_RISK_MARKERS = {"D", "E", "F", "U", "2", "1", "Fail", "不及格"}


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _grade_token(value: str) -> str:
    return str(value or "").strip().upper()


def _academic_profile(p: dict) -> dict[str, Any]:
    courses = p["courses"]["items"]
    grades = p["courses"]["grades"]
    curricula = list(p["courses"].get("curricula") or [])
    if p["courses"].get("custom_curriculum"):
        curricula = curricula + [f"Custom:{p['courses']['custom_curriculum']}"]

    actual = [g for g in grades if g.get("grade_type") == "Actual" or (g.get("grade") and not g.get("is_predicted") and g.get("grade_type") != "Predicted")]
    predicted = [g for g in grades if g.get("is_predicted") or g.get("grade_type") == "Predicted"]

    strengths = []
    weaknesses = []
    for g in actual + predicted:
        subject = g.get("subject") or "未命名科目"
        token = _grade_token(g.get("grade") or g.get("score"))
        if any(m.upper() in token for m in _STRONG_MARKERS):
            label = f"{subject} 成绩表现相对突出"
            if label not in strengths:
                strengths.append(label)
        if any(m.upper() == token or token.endswith(m.upper()) for m in _RISK_MARKERS):
            label = f"{subject} 成绩存在风险信号，建议复核"
            if label not in weaknesses:
                weaknesses.append(label)

    missing = []
    if not courses:
        missing.append("课程未填写")
    if not actual:
        missing.append("尚无 Actual 成绩")
    if not predicted:
        missing.append("预测成绩尚不完整")
    if not curricula:
        missing.append("课程体系未选择")

    rigor = "未确认"
    if any(c in ("A-Level", "IB", "AP") for c in curricula):
        rigor = "课程体系通常具有较高学术强度（仅作结构提示）"
    elif curricula:
        rigor = "已登记课程体系，强度需结合学校与科目确认"

    trend = "数据不足，暂无法判断趋势"
    if len(actual) >= 2 or (actual and predicted):
        trend = "已有多条成绩记录，可继续按学年补充以观察趋势（非诊断结论）"

    return {
        "curricula": curricula,
        "courses": [{"id": c.get("id"), "subject": c.get("subject"), "qualification": c.get("qualification"), "level": c.get("level")} for c in courses],
        "actual_grades": actual,
        "predicted_grades": predicted,
        "academic_strengths": strengths[:8],
        "academic_weaknesses": weaknesses[:8],
        "grade_trend": trend,
        "curriculum_rigor": rigor,
        "missing_academic_data": missing,
    }


def _language_profile(p: dict) -> dict[str, Any]:
    exams = p["courses"].get("language_exams") or []
    rows = []
    for ex in exams:
        score = str(ex.get("overall_score") or "").strip()
        # Without official university cutoffs we never invent "已满足".
        status = "待确认" if score else "缺失"
        rows.append(
            {
                "exam_type": ex.get("exam_type") or "Other",
                "exam_date": ex.get("exam_date") or "",
                "overall_score": score,
                "status": status,
                "notes": ex.get("notes") or "",
            }
        )
    if not rows:
        rows = [
            {"exam_type": "IELTS", "exam_date": "", "overall_score": "", "status": "缺失", "notes": ""},
            {"exam_type": "TOEFL", "exam_date": "", "overall_score": "", "status": "缺失", "notes": ""},
            {"exam_type": "HSK", "exam_date": "", "overall_score": "", "status": "缺失", "notes": ""},
            {"exam_type": "Duolingo", "exam_date": "", "overall_score": "", "status": "缺失", "notes": ""},
        ]
    filled = sum(1 for r in rows if r["overall_score"])
    return {
        "exams": rows,
        "filled_count": filled,
        "summary": "已有语言成绩记录" if filled else "语言成绩缺失",
    }


def _identity_profile(p: dict) -> dict[str, Any]:
    intl = dict(p["identity"]["international"])
    hq = dict(p["identity"]["huaqiao"])
    # Portrait must never rewrite eligibility engine verdicts.
    return {
        "international": {
            "status": intl.get("status") or "NOT_ASSESSED",
            "engine_result": intl.get("engine_result") or "",
            "conclusion": intl.get("conclusion") or "",
            "confirmed": bool(intl.get("confirmed")),
            "assessed_at": intl.get("assessed_at") or "",
            "policy_version": intl.get("policy_version") or "",
            "needs_assessment": (intl.get("status") or "NOT_ASSESSED") == "NOT_ASSESSED",
            "prompt": "尚未完成身份判定" if (intl.get("status") or "NOT_ASSESSED") == "NOT_ASSESSED" else "",
        },
        "huaqiao": {
            "status": hq.get("status") or "NOT_ASSESSED",
            "engine_result": hq.get("engine_result") or "",
            "conclusion": hq.get("conclusion") or "",
            "confirmed": bool(hq.get("confirmed")),
            "assessed_at": hq.get("assessed_at") or "",
            "policy_version": hq.get("policy_version") or "",
            "needs_assessment": (hq.get("status") or "NOT_ASSESSED") == "NOT_ASSESSED",
            "prompt": "尚未完成身份判定" if (hq.get("status") or "NOT_ASSESSED") == "NOT_ASSESSED" else "",
        },
        "facts": {
            "has_foreign_nationality": bool(p["identity"].get("has_foreign_nationality")),
            "has_chinese_nationality": bool(p["identity"].get("has_chinese_nationality")),
            "current_nationality": p["identity"].get("current_nationality") or "",
            "birth_country": p["identity"].get("birth_country") or "",
        },
    }


def _target_profile(p: dict) -> dict[str, Any]:
    targets = p["goals"]["targets"]
    counts = {k: 0 for k in PRIORITY_LEVELS}
    countries = []
    universities = []
    majors = []
    years = []
    for t in targets:
        level = t.get("priority_level") or "target"
        if level in counts:
            counts[level] += 1
        if t.get("country"):
            countries.append(t["country"])
        if t.get("university_name"):
            universities.append(t["university_name"])
        if t.get("major"):
            majors.append(t["major"])
        if t.get("entry_year"):
            years.append(str(t["entry_year"]))
    flags = []
    if not targets:
        flags.append("NO_TARGETS")
    if targets and counts.get("safety", 0) == 0:
        flags.append("NO_SAFETY")
    if counts.get("reach", 0) >= 4 and counts.get("safety", 0) == 0:
        flags.append("TOO_MANY_REACH")
    if targets and not majors:
        flags.append("NO_MAJOR")
    entry = p["basic_info"].get("intended_entry_year") or ""
    if not entry and not years:
        flags.append("ENTRY_YEAR_MISSING")
    return {
        "counts": counts,
        "countries": sorted(set(countries)),
        "universities": universities,
        "majors": majors,
        "entry_years": sorted(set(years + ([entry] if entry else []))),
        "structure_flags": flags,
        "targets": targets,
    }


def _readiness(p: dict, academic: dict, language: dict, identity: dict, targets: dict) -> dict[str, Any]:
    profile_c = completeness(p)
    academic_ok = 100 if not academic["missing_academic_data"] else max(0, 100 - 20 * len(academic["missing_academic_data"]))
    lang_ok = 100 if language["filled_count"] else 0
    id_parts = []
    id_parts.append(identity["international"]["status"] != "NOT_ASSESSED")
    id_parts.append(identity["huaqiao"]["status"] != "NOT_ASSESSED")
    identity_ok = round(100 * sum(1 for x in id_parts if x) / len(id_parts))
    target_ok = 100
    if "NO_TARGETS" in targets["structure_flags"]:
        target_ok = 0
    else:
        deductions = 0
        if "NO_SAFETY" in targets["structure_flags"]:
            deductions += 25
        if "NO_MAJOR" in targets["structure_flags"]:
            deductions += 20
        if "ENTRY_YEAR_MISSING" in targets["structure_flags"]:
            deductions += 20
        if "TOO_MANY_REACH" in targets["structure_flags"]:
            deductions += 15
        target_ok = max(0, 100 - deductions)
    exam_ok = 100 if (academic["actual_grades"] or academic["predicted_grades"]) and language["filled_count"] else (50 if academic["actual_grades"] or academic["predicted_grades"] or language["filled_count"] else 0)
    timeline_ok = 100 if (p["basic_info"].get("intended_entry_year") and targets["universities"]) else (40 if targets["universities"] or p["basic_info"].get("intended_entry_year") else 0)

    components = {
        "profile_completion": profile_c["percent"],
        "academic_completion": academic_ok,
        "identity_completion": identity_ok,
        "target_completion": target_ok,
        "exam_completion": exam_ok,
        "timeline_readiness": timeline_ok,
    }
    score = round(sum(components.values()) / len(components))
    missing = list(profile_c["missing"])
    return {"score": score, "components": components, "missing": missing}


def _risk_and_actions(p: dict, academic: dict, language: dict, identity: dict, targets: dict, timeline_summary: dict | None) -> tuple[list[str], list[dict]]:
    risks = []
    actions = []
    if identity["international"]["needs_assessment"]:
        risks.append("身份尚未判定（国际生）")
        actions.append({"code": "ASSESS_INTERNATIONAL", "label": "完成国际生资格判定", "section": "identity"})
    if identity["huaqiao"]["needs_assessment"]:
        risks.append("身份尚未判定（华侨生）")
        actions.append({"code": "ASSESS_HUAQIAO", "label": "完成华侨生资格判定", "section": "identity"})
    if "预测成绩尚不完整" in academic["missing_academic_data"] or "预测成绩缺失" in completeness(p)["missing"]:
        risks.append("预测成绩缺失")
        actions.append({"code": "ADD_PREDICTED", "label": "补充 A-Level / 课程预测成绩", "section": "courses"})
    if language["filled_count"] == 0:
        risks.append("语言成绩缺失")
        actions.append({"code": "ADD_LANGUAGE", "label": "补充语言成绩", "section": "courses"})
    if "NO_SAFETY" in targets["structure_flags"]:
        risks.append("没有保底学校")
        actions.append({"code": "ADD_SAFETY", "label": "添加至少一个保底大学", "section": "goals"})
    if "ENTRY_YEAR_MISSING" in targets["structure_flags"]:
        risks.append("目标入学年份缺失")
        actions.append({"code": "ADD_ENTRY_YEAR", "label": "填写预计入学年份", "section": "basic_info"})
    if "NO_TARGETS" in targets["structure_flags"] or len(targets["universities"]) < 2:
        risks.append("目标大学过少")
        actions.append({"code": "ADD_TARGETS", "label": "补充目标大学列表", "section": "goals"})
    tl = timeline_summary or {}
    if tl.get("overdue_count"):
        risks.append("重要申请节点已逾期")
        actions.append({"code": "OPEN_TIMELINE_OVERDUE", "label": "处理逾期时间轴事项", "section": "timeline"})
    if tl.get("next_30_count"):
        actions.append({"code": "OPEN_TIMELINE_30", "label": "检查未来 30 天申请节点", "section": "timeline"})
    elif tl.get("next_90_count"):
        actions.append({"code": "OPEN_TIMELINE_90", "label": "检查未来 90 天申请节点", "section": "timeline"})
    else:
        actions.append({"code": "GENERATE_TIMELINE", "label": "生成/刷新个人升学时间轴", "section": "timeline"})

    # de-dupe actions preserving order, max 5
    seen = set()
    uniq = []
    for a in actions:
        if a["code"] in seen:
            continue
        seen.add(a["code"])
        uniq.append(a)
        if len(uniq) >= 5:
            break
    return risks, uniq


def build_student_portrait(profile: dict, timeline_summary: dict | None = None) -> dict[str, Any]:
    """Pure function: profile (+ optional timeline summary) -> portrait JSON."""
    p = normalize_profile(profile)
    basic = p["basic_info"]
    current = p["education"]["current_school"]
    academic = _academic_profile(p)
    language = _language_profile(p)
    identity = _identity_profile(p)
    targets = _target_profile(p)
    readiness = _readiness(p, academic, language, identity, targets)
    risks, actions = _risk_and_actions(p, academic, language, identity, targets, timeline_summary)

    return {
        "portrait_version": PORTRAIT_VERSION,
        "portrait_generated_at": _now_iso(),
        "profile_updated_at": p.get("updated_at") or "",
        "basic": {
            "chinese_name": basic.get("chinese_name") or "",
            "english_name": basic.get("english_name") or "",
            "age": age_from_birth_date(basic.get("birth_date") or ""),
            "birth_date": basic.get("birth_date") or "",
            "current_country": basic.get("current_country") or current.get("country") or "",
            "current_school": current.get("school_name") or "",
            "current_grade": current.get("current_grade") or "",
            "curricula": academic["curricula"],
            "intended_entry_year": basic.get("intended_entry_year") or "",
        },
        "academic": academic,
        "language": language,
        "identity": identity,
        "targets": targets,
        "application_readiness": readiness,
        "risk_flags": risks,
        "next_actions": actions,
        "timeline_summary": timeline_summary or {
            "overdue_count": 0,
            "next_30_count": 0,
            "next_90_count": 0,
            "next_30": [],
            "next_90": [],
        },
        "completeness": completeness(p),
    }


class StudentPortraitService:
    """Service wrapper for deterministic portrait generation."""

    version = PORTRAIT_VERSION

    def generate(self, profile: dict, timeline_summary: dict | None = None) -> dict[str, Any]:
        return build_student_portrait(profile, timeline_summary)
