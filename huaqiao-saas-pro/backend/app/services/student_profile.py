"""Student Master Profile v2 — schema, legacy vault compatibility, section merge.

Does not change international or overseas-Chinese eligibility engines.
Old vault JSON fields are preserved under profile['legacy'] and projected back.
"""
from __future__ import annotations

import copy
import uuid
from datetime import datetime, date
from typing import Any

SCHEMA_VERSION = 2

SCHOOL_TYPES = [
    "Public School",
    "Private School",
    "Grammar School",
    "International School",
    "Chinese High School",
    "College",
    "University",
    "Other",
]

CURRICULUMS = [
    "A-Level",
    "GCSE",
    "IGCSE",
    "IB",
    "AP",
    "SAT",
    "ACT",
    "Canadian High School",
    "Australian Curriculum",
    "Chinese High School",
    "HK Curriculum",
    "Other",
    "Custom",
]

GRADE_TYPES = ["Actual", "Predicted", "Mock", "School Assessment", "Other"]

LANGUAGE_EXAMS = ["HSK", "IELTS", "TOEFL", "Duolingo", "Other"]

OTHER_EXAM_TYPES = ["CSCA", "SAT", "ACT", "AP", "竞赛", "其他资格"]

PRIORITY_LEVELS = {
    "reach": "冲刺",
    "target": "主申",
    "match": "稳妥",
    "safety": "保底",
}

ELIGIBILITY_STATUSES = [
    "NOT_ASSESSED",
    "IN_PROGRESS",
    "ELIGIBLE",
    "LIKELY_ELIGIBLE",
    "NOT_ELIGIBLE",
    "NEED_MORE_INFO",
]

SECTION_NOTES = {
    "basic_info": "basic_info_notes",
    "education": "education_notes",
    "courses": "courses_notes",
    "goals": "goals_notes",
    "identity": "identity_notes",
    "planning": "planning_notes",
    "summary": "summary_notes",
}

SECTIONS = list(SECTION_NOTES.keys())

LEGACY_VAULT_KEYS = (
    "family_note",
    "child_identity",
    "residence_note",
    "goal_note",
    "intended_major",
    "target_schools",
    "school",
    "subjects",
    "predicted_grade",
    "target_university",
    "target_major",
    "nationality",
    "notes",
)


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def new_id() -> str:
    return uuid.uuid4().hex


def empty_school(**overrides) -> dict[str, Any]:
    row = {
        "id": new_id(),
        "school_name": "",
        "country": "",
        "city": "",
        "school_type": "",
        "start_date": "",
        "end_date": "",
        "current_grade": "",
        "is_current": False,
        "sort_order": 0,
        "notes": "",
    }
    row.update(overrides)
    return row


def empty_course(**overrides) -> dict[str, Any]:
    row = {
        "id": new_id(),
        "subject": "",
        "qualification": "",
        "level": "",
        "exam_board": "",
        "start_year": "",
        "end_year": "",
        "is_current": False,
        "notes": "",
    }
    row.update(overrides)
    return row


def empty_grade(**overrides) -> dict[str, Any]:
    row = {
        "id": new_id(),
        "course_id": "",
        "subject": "",
        "academic_year": "",
        "exam_session": "",
        "grade_type": "Actual",
        "grade": "",
        "score": "",
        "max_score": "",
        "exam_board": "",
        "is_predicted": False,
        "notes": "",
    }
    row.update(overrides)
    return row


def empty_language_exam(**overrides) -> dict[str, Any]:
    row = {
        "id": new_id(),
        "exam_type": "",
        "exam_date": "",
        "overall_score": "",
        "sub_scores": {},
        "certificate_no": "",
        "notes": "",
    }
    row.update(overrides)
    return row


def empty_other_exam(**overrides) -> dict[str, Any]:
    row = {
        "id": new_id(),
        "exam_type": "",
        "custom_type": "",
        "exam_date": "",
        "score": "",
        "notes": "",
    }
    row.update(overrides)
    return row


def empty_target(**overrides) -> dict[str, Any]:
    row = {
        "id": new_id(),
        "country": "中国",
        "university_id": None,
        "university_name": "",
        "major": "",
        "college": "",
        "entry_year": "",
        "application_route": "",
        "priority_level": "target",
        "notes": "",
        "sort_order": 0,
    }
    row.update(overrides)
    return row


def empty_eligibility_card() -> dict[str, Any]:
    return {
        "status": "NOT_ASSESSED",
        "engine_result": "",
        "conclusion": "",
        "assessed_at": "",
        "policy_version": "",
        "record_id": None,
        "confirmed": False,
        "confirmed_at": "",
    }


def empty_profile() -> dict[str, Any]:
    current = empty_school(is_current=True)
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "wizard_completed": False,
        "basic_info": {
            "chinese_name": "",
            "english_name": "",
            "birth_date": "",
            "gender": "",
            "current_country": "",
            "current_city": "",
            "contact": "",
            "intended_entry_year": "",
            "profile_created_at": _now_iso(),
            "basic_info_notes": "",
        },
        "education": {
            "current_school": current,
            "history": [copy.deepcopy(current)],
            "education_notes": "",
        },
        "courses": {
            "curricula": [],
            "custom_curriculum": "",
            "items": [],
            "grades": [],
            "language_exams": [],
            "other_exams": [],
            "courses_notes": "",
        },
        "goals": {
            "targets": [],
            "goals_notes": "",
        },
        "identity": {
            "birth_country": "",
            "current_nationality": "",
            "former_nationalities": "",
            "had_chinese_nationality": False,
            "has_chinese_hukou": False,
            "hukou_cancelled": False,
            "foreign_nationality_acquired_date": "",
            "foreign_permanent_residence": "",
            "passport_info": "",
            "father_nationality": "",
            "mother_nationality": "",
            "parents_overseas_settlement": "",
            "overseas_residence_info": "",
            "has_foreign_nationality": False,
            "has_chinese_nationality": False,
            "international": empty_eligibility_card(),
            "huaqiao": empty_eligibility_card(),
            "identity_notes": "",
        },
        "planning": {
            "current_education_stage": "",
            "target_countries": "",
            "planning_notes": "",
        },
        "summary": {
            "summary_notes": "",
        },
        "legacy": {},
    }


def _as_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _split_schools(raw: str) -> list[str]:
    if not raw:
        return []
    parts = []
    for chunk in str(raw).replace("；", "\n").replace(";", "\n").replace("，", "\n").replace(",", "\n").split("\n"):
        name = chunk.strip()
        if name:
            parts.append(name)
    return parts


def migrate_legacy_vault(old: dict | None) -> dict[str, Any]:
    """Convert vault v1 / ad-hoc student fields into Master Profile v2.

    Never drops unknown keys; they live in profile['legacy'].
    """
    src = dict(old or {})
    profile = empty_profile()
    if not src:
        return profile

    leftover = {}
    for key, value in src.items():
        leftover[key] = value

    basic = profile["basic_info"]
    basic["chinese_name"] = str(src.get("chinese_name") or src.get("name") or "")
    basic["english_name"] = str(src.get("english_name") or "")
    basic["birth_date"] = str(src.get("birth_date") or "")
    basic["gender"] = str(src.get("gender") or "")
    basic["current_country"] = str(src.get("current_country") or src.get("country") or "")
    basic["current_city"] = str(src.get("current_city") or src.get("city") or "")
    basic["contact"] = str(src.get("contact") or src.get("phone") or src.get("email") or "")
    basic["intended_entry_year"] = str(src.get("intended_entry_year") or src.get("entry_year") or "")
    basic["basic_info_notes"] = str(src.get("basic_info_notes") or src.get("family_note") or "")

    school_name = str(src.get("school") or src.get("school_name") or "")
    if school_name:
        current = empty_school(school_name=school_name, is_current=True)
        profile["education"]["current_school"] = current
        profile["education"]["history"] = [copy.deepcopy(current)]
    profile["education"]["education_notes"] = str(src.get("education_notes") or "")

    subjects_raw = src.get("subjects") or src.get("courses") or ""
    if isinstance(subjects_raw, str) and subjects_raw.strip():
        for subject in _split_schools(subjects_raw):
            profile["courses"]["items"].append(empty_course(subject=subject, is_current=True))
    elif isinstance(subjects_raw, list):
        for item in subjects_raw:
            if isinstance(item, str) and item.strip():
                profile["courses"]["items"].append(empty_course(subject=item.strip(), is_current=True))
            elif isinstance(item, dict):
                profile["courses"]["items"].append(empty_course(**{k: v for k, v in item.items() if k in empty_course()}))

    predicted = str(src.get("predicted_grade") or "")
    if predicted and profile["courses"]["items"]:
        first = profile["courses"]["items"][0]
        profile["courses"]["grades"].append(
            empty_grade(
                course_id=first["id"],
                subject=first["subject"],
                grade_type="Predicted",
                grade=predicted,
                is_predicted=True,
            )
        )
    elif predicted:
        profile["courses"]["grades"].append(
            empty_grade(grade_type="Predicted", grade=predicted, is_predicted=True)
        )
    profile["courses"]["courses_notes"] = str(src.get("courses_notes") or "")

    targets: list[dict] = []
    school_blob = src.get("target_schools") or src.get("target_university") or ""
    major_blob = str(src.get("intended_major") or src.get("target_major") or "")
    if isinstance(src.get("targets"), list):
        for item in src["targets"]:
            if isinstance(item, dict):
                targets.append(empty_target(**{k: v for k, v in item.items() if k in empty_target()}))
    names = _split_schools(str(school_blob)) if not targets else []
    for idx, name in enumerate(names):
        targets.append(
            empty_target(
                university_name=name,
                major=major_blob if idx == 0 else "",
                priority_level="target",
                sort_order=idx,
            )
        )
    if not names and major_blob:
        targets.append(empty_target(major=major_blob, priority_level="target"))
    profile["goals"]["targets"] = targets
    profile["goals"]["goals_notes"] = str(src.get("goals_notes") or src.get("goal_note") or "")

    identity = profile["identity"]
    identity["current_nationality"] = str(src.get("nationality") or src.get("current_nationality") or "")
    identity["passport_info"] = str(src.get("passport_info") or "")
    identity["overseas_residence_info"] = str(src.get("residence_note") or "")
    identity["parents_overseas_settlement"] = str(src.get("family_note") or "")
    child = str(src.get("child_identity") or "")
    if child:
        identity["identity_notes"] = child
        identity["current_nationality"] = identity["current_nationality"] or child
    else:
        identity["identity_notes"] = str(src.get("identity_notes") or "")
    if src.get("has_foreign_nationality") is True:
        identity["has_foreign_nationality"] = True
    if src.get("has_chinese_nationality") is True:
        identity["has_chinese_nationality"] = True

    profile["planning"]["planning_notes"] = str(src.get("planning_notes") or "")
    profile["summary"]["summary_notes"] = str(src.get("summary_notes") or src.get("notes") or "")

    known = {
        "chinese_name", "english_name", "name", "birth_date", "gender", "current_country", "country",
        "current_city", "city", "contact", "phone", "email", "intended_entry_year", "entry_year",
        "school", "school_name", "subjects", "courses", "predicted_grade", "target_schools",
        "target_university", "intended_major", "target_major", "targets", "nationality",
        "current_nationality", "passport_info", "has_foreign_nationality", "has_chinese_nationality",
        "schema_version", "students", "id", "basic_info", "education", "goals", "identity",
        "planning", "summary", "legacy", "wizard_completed", "created_at", "updated_at",
        *LEGACY_VAULT_KEYS, *SECTION_NOTES.values(),
    }
    profile["legacy"] = {k: v for k, v in leftover.items() if k not in known}
    for key in LEGACY_VAULT_KEYS:
        if key in src:
            profile["legacy"][key] = src[key]
    profile["wizard_completed"] = bool(basic["chinese_name"] or school_name or targets)
    return normalize_profile(profile)


def normalize_profile(raw: dict | None) -> dict[str, Any]:
    """Ensure a stored document always has v2 keys; keep extra nested data."""
    if not raw:
        return empty_profile()
    if raw.get("schema_version") != SCHEMA_VERSION or "basic_info" not in raw:
        if any(k in raw for k in LEGACY_VAULT_KEYS) and "basic_info" not in raw:
            return migrate_legacy_vault(raw)
    base = empty_profile()
    out = copy.deepcopy(base)
    out["schema_version"] = SCHEMA_VERSION
    out["created_at"] = raw.get("created_at") or base["created_at"]
    out["updated_at"] = raw.get("updated_at") or base["updated_at"]
    out["wizard_completed"] = bool(raw.get("wizard_completed"))
    out["legacy"] = {**base["legacy"], **_as_dict(raw.get("legacy"))}

    for section in SECTIONS:
        incoming = _as_dict(raw.get(section))
        merged = copy.deepcopy(base[section])
        if section == "education":
            current = {**merged["current_school"], **_as_dict(incoming.get("current_school"))}
            if not current.get("id"):
                current["id"] = new_id()
            history = []
            for idx, item in enumerate(_as_list(incoming.get("history"))):
                row = empty_school(**{k: v for k, v in _as_dict(item).items() if k in empty_school()})
                if _as_dict(item).get("id"):
                    row["id"] = item["id"]
                row["sort_order"] = item.get("sort_order", idx) if isinstance(item, dict) else idx
                history.append(row)
            if not history and current.get("school_name"):
                history = [copy.deepcopy(current)]
            merged["current_school"] = current
            merged["history"] = history
            merged["education_notes"] = incoming.get("education_notes", merged["education_notes"])
        elif section == "courses":
            merged["curricula"] = list(_as_list(incoming.get("curricula")))
            merged["custom_curriculum"] = str(incoming.get("custom_curriculum") or "")
            items = []
            for item in _as_list(incoming.get("items") or incoming.get("courses")):
                row = empty_course(**{k: v for k, v in _as_dict(item).items() if k in empty_course()})
                if _as_dict(item).get("id"):
                    row["id"] = item["id"]
                items.append(row)
            grades = []
            for item in _as_list(incoming.get("grades")):
                row = empty_grade(**{k: v for k, v in _as_dict(item).items() if k in empty_grade()})
                if _as_dict(item).get("id"):
                    row["id"] = item["id"]
                row["is_predicted"] = bool(item.get("is_predicted") or item.get("grade_type") == "Predicted") if isinstance(item, dict) else False
                grades.append(row)
            langs = []
            for item in _as_list(incoming.get("language_exams")):
                row = empty_language_exam(**{k: v for k, v in _as_dict(item).items() if k in empty_language_exam()})
                if _as_dict(item).get("id"):
                    row["id"] = item["id"]
                langs.append(row)
            others = []
            for item in _as_list(incoming.get("other_exams")):
                row = empty_other_exam(**{k: v for k, v in _as_dict(item).items() if k in empty_other_exam()})
                if _as_dict(item).get("id"):
                    row["id"] = item["id"]
                others.append(row)
            merged["items"] = items
            merged["grades"] = grades
            merged["language_exams"] = langs
            merged["other_exams"] = others
            merged["courses_notes"] = incoming.get("courses_notes", merged["courses_notes"])
        elif section == "goals":
            targets = []
            for idx, item in enumerate(_as_list(incoming.get("targets"))):
                row = empty_target(**{k: v for k, v in _as_dict(item).items() if k in empty_target()})
                if _as_dict(item).get("id"):
                    row["id"] = item["id"]
                level = str(row.get("priority_level") or "target").lower()
                if level not in PRIORITY_LEVELS:
                    level = "target"
                row["priority_level"] = level
                row["sort_order"] = item.get("sort_order", idx) if isinstance(item, dict) else idx
                targets.append(row)
            merged["targets"] = targets
            merged["goals_notes"] = incoming.get("goals_notes", merged["goals_notes"])
        elif section == "identity":
            for key in list(merged.keys()):
                if key in ("international", "huaqiao"):
                    card = {**empty_eligibility_card(), **_as_dict(incoming.get(key))}
                    if card.get("status") not in ELIGIBILITY_STATUSES:
                        card["status"] = "NOT_ASSESSED"
                    merged[key] = card
                elif key in incoming:
                    merged[key] = incoming[key]
        else:
            merged.update({k: v for k, v in incoming.items() if k in merged or k.endswith("_notes")})
        notes_key = SECTION_NOTES[section]
        if notes_key in incoming:
            merged[notes_key] = incoming[notes_key]
        elif notes_key in raw:
            merged[notes_key] = raw[notes_key]
        out[section] = merged

    sync_current_school(out)
    return out


def sync_current_school(profile: dict) -> dict:
    history = _as_list(profile.get("education", {}).get("history"))
    current = None
    for item in history:
        if item.get("is_current"):
            current = item
            break
    if current is None and history:
        current = history[0]
        current["is_current"] = True
    if current is None:
        current = empty_school(is_current=True)
        history = [current]
    profile.setdefault("education", {})
    profile["education"]["current_school"] = copy.deepcopy(current)
    profile["education"]["history"] = history
    return profile


def merge_section(profile: dict, section: str, payload: dict) -> dict:
    if section not in SECTIONS:
        raise ValueError(f"未知档案分节: {section}")
    out = normalize_profile(profile)
    data = _as_dict(payload)
    notes_key = SECTION_NOTES[section]
    # Do not let a generic "notes" field overwrite per-section notes.
    data.pop("notes", None)
    if notes_key in payload:
        data[notes_key] = payload[notes_key]
    wrapped = {section: {**out[section], **data}}
    merged = normalize_profile({**out, **wrapped})
    merged["updated_at"] = _now_iso()
    return merged


def project_legacy_vault(profile: dict) -> dict[str, Any]:
    """Flat fields so the old vault UI / clients keep working."""
    p = normalize_profile(profile)
    basic = p["basic_info"]
    current = p["education"]["current_school"]
    targets = p["goals"]["targets"]
    first_target = targets[0] if targets else {}
    subjects = "、".join(c.get("subject") or "" for c in p["courses"]["items"] if c.get("subject"))
    predicted = next((g.get("grade") for g in p["courses"]["grades"] if g.get("is_predicted") or g.get("grade_type") == "Predicted"), "")
    school_names = "\n".join(t.get("university_name") or "" for t in targets if t.get("university_name"))
    out = {
        "family_note": p["identity"].get("parents_overseas_settlement") or p["legacy"].get("family_note", ""),
        "child_identity": p["identity"].get("identity_notes") or p["legacy"].get("child_identity", ""),
        "residence_note": p["identity"].get("overseas_residence_info") or p["legacy"].get("residence_note", ""),
        "goal_note": p["goals"].get("goals_notes") or p["legacy"].get("goal_note", ""),
        "intended_major": first_target.get("major") or p["legacy"].get("intended_major", ""),
        "target_schools": school_names or p["legacy"].get("target_schools", ""),
        "school": current.get("school_name") or p["legacy"].get("school", ""),
        "subjects": subjects or p["legacy"].get("subjects", ""),
        "predicted_grade": predicted or p["legacy"].get("predicted_grade", ""),
        "target_university": first_target.get("university_name") or p["legacy"].get("target_university", ""),
        "target_major": first_target.get("major") or p["legacy"].get("target_major", ""),
        "nationality": p["identity"].get("current_nationality") or p["legacy"].get("nationality", ""),
        "schema_version": SCHEMA_VERSION,
    }
    for key, value in _as_dict(p.get("legacy")).items():
        out.setdefault(key, value)
    out["name"] = basic.get("chinese_name") or ""
    return out


def map_engine_result(engine_result: str | None) -> str:
    mapping = {
        "PRELIMINARY_ELIGIBLE": "LIKELY_ELIGIBLE",
        "MANUAL_REVIEW_REQUIRED": "NEED_MORE_INFO",
        "PRELIMINARY_INELIGIBLE": "NOT_ELIGIBLE",
        "ELIGIBLE": "ELIGIBLE",
        "LIKELY_ELIGIBLE": "LIKELY_ELIGIBLE",
        "NOT_ELIGIBLE": "NOT_ELIGIBLE",
        "NEED_MORE_INFO": "NEED_MORE_INFO",
        "IN_PROGRESS": "IN_PROGRESS",
        "NOT_ASSESSED": "NOT_ASSESSED",
    }
    return mapping.get(str(engine_result or ""), "NEED_MORE_INFO")


def apply_eligibility_result(profile: dict, kind: str, engine_payload: dict, *, confirm: bool = False) -> dict:
    if kind not in ("international", "huaqiao"):
        raise ValueError("判定类型必须是 international 或 huaqiao")
    out = normalize_profile(profile)
    card = out["identity"][kind]
    raw_result = engine_payload.get("result") or engine_payload.get("engine_result") or ""
    card["engine_result"] = raw_result
    card["status"] = map_engine_result(raw_result)
    card["conclusion"] = str(engine_payload.get("conclusion") or engine_payload.get("explanation") or "")
    card["assessed_at"] = engine_payload.get("assessed_at") or _now_iso()
    card["policy_version"] = str(engine_payload.get("policy_version") or "R4.2")
    card["record_id"] = engine_payload.get("record_id")
    if confirm:
        card["confirmed"] = True
        card["confirmed_at"] = _now_iso()
        if card["status"] == "LIKELY_ELIGIBLE":
            card["status"] = "ELIGIBLE"
    else:
        card["confirmed"] = False
        card["confirmed_at"] = ""
    out["identity"][kind] = card
    out["updated_at"] = _now_iso()
    return out


def age_from_birth_date(birth_date: str) -> int | None:
    text = (birth_date or "").strip()[:10]
    if len(text) < 8:
        return None
    try:
        born = date.fromisoformat(text.replace("/", "-"))
    except ValueError:
        return None
    today = date.today()
    years = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return years if years >= 0 else None


def completeness(profile: dict) -> dict[str, Any]:
    p = normalize_profile(profile)
    missing: list[str] = []
    checks = []

    def add(ok: bool, label: str):
        checks.append(ok)
        if not ok:
            missing.append(label)

    basic = p["basic_info"]
    add(bool(basic.get("chinese_name") or basic.get("english_name")), "姓名未填写")
    add(bool(basic.get("birth_date")), "出生日期未填写")
    add(bool(p["education"]["current_school"].get("school_name")), "当前学校未填写")
    add(bool(p["courses"].get("curricula") or p["courses"].get("custom_curriculum")), "课程体系未选择")
    add(bool(p["courses"].get("items")), "课程未填写")
    has_predicted = any(g.get("is_predicted") or g.get("grade_type") == "Predicted" for g in p["courses"]["grades"])
    has_actual = any(g.get("grade_type") == "Actual" or (g.get("grade") and not g.get("is_predicted")) for g in p["courses"]["grades"])
    add(has_actual or has_predicted, "成绩未填写")
    add(has_predicted, "预测成绩缺失")
    add(bool(p["courses"].get("language_exams")), "语言成绩未填写")
    add(bool(p["goals"].get("targets")), "目标大学未填写")
    intl = p["identity"]["international"]["status"]
    hq = p["identity"]["huaqiao"]["status"]
    add(intl != "NOT_ASSESSED", "国际生尚未判定")
    add(hq != "NOT_ASSESSED", "华侨生尚未判定")
    add(bool(basic.get("intended_entry_year")), "预计入学年份未填写")

    total = len(checks) or 1
    percent = round(100 * sum(1 for x in checks if x) / total)
    return {"percent": percent, "missing": missing, "total": total, "filled": sum(1 for x in checks if x)}


def profile_summary(profile: dict) -> dict[str, Any]:
    p = normalize_profile(profile)
    current = p["education"]["current_school"]
    courses = p["courses"]["items"][:6]
    grades = p["courses"]["grades"][:6]
    langs = p["courses"]["language_exams"]
    targets = p["goals"]["targets"]
    counts = {key: 0 for key in PRIORITY_LEVELS}
    for t in targets:
        level = t.get("priority_level") or "target"
        if level in counts:
            counts[level] += 1
    latest_grade = grades[-1] if grades else {}
    return {
        "chinese_name": p["basic_info"].get("chinese_name") or "",
        "english_name": p["basic_info"].get("english_name") or "",
        "birth_date": p["basic_info"].get("birth_date") or "",
        "age": age_from_birth_date(p["basic_info"].get("birth_date") or ""),
        "current_school": current.get("school_name") or "",
        "curricula": p["courses"].get("curricula") or [],
        "custom_curriculum": p["courses"].get("custom_curriculum") or "",
        "main_courses": [c.get("subject") for c in courses if c.get("subject")],
        "latest_grade": latest_grade,
        "language_exams": langs,
        "international_status": p["identity"]["international"]["status"],
        "huaqiao_status": p["identity"]["huaqiao"]["status"],
        "intended_entry_year": p["basic_info"].get("intended_entry_year") or "",
        "target_universities": [t.get("university_name") for t in targets if t.get("university_name")],
        "priority_counts": counts,
        "completeness": completeness(p),
    }


def display_name_of(profile: dict) -> str:
    p = normalize_profile(profile)
    return p["basic_info"].get("chinese_name") or p["basic_info"].get("english_name") or "未命名学生"


def judge_prefills(profile: dict) -> dict[str, Any]:
    """Facts only — never a self-declared eligibility label."""
    p = normalize_profile(profile)
    basic = p["basic_info"]
    ident = p["identity"]
    return {
        "name": basic.get("chinese_name") or basic.get("english_name") or "",
        "birth_date": basic.get("birth_date") or "",
        "current_nationality": ident.get("current_nationality") or "",
        "has_foreign_nationality": bool(ident.get("has_foreign_nationality")),
        "has_chinese_nationality": bool(ident.get("has_chinese_nationality")),
        "foreign_nationality_acquired_date": ident.get("foreign_nationality_acquired_date") or "",
        "passport_info": ident.get("passport_info") or "",
        "has_mainland_household": bool(ident.get("has_chinese_hukou")) and not bool(ident.get("hukou_cancelled")),
        "born_abroad": bool(ident.get("birth_country") and ident.get("birth_country") not in ("中国", "中国大陆", "CN")),
        "intended_entry_year": basic.get("intended_entry_year") or "",
    }
