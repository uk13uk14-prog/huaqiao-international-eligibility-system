
from sqlalchemy.orm import Session
from ..models import AdmissionSchedule, University

FIELD_ALIASES = {
    "综合": ["综合"],
    "理工": ["理工"],
    "文史": ["文史"],
    "医药": ["医药"],
    "体育": ["体育"],
    "音乐": ["音乐"],
    "美术": ["美术"],
    "设计": ["设计"],
}


def _score_band(score: int | None) -> tuple[int, str]:
    if score is None or score <= 0:
        return 999, "未填写成绩，按专业领域与学校层次综合推荐。"
    if score >= 680:
        return 20, "成绩竞争力强，优先推荐顶尖与 C9/985 高校。"
    if score >= 620:
        return 40, "成绩较有竞争力，优先推荐 985/211/双一流高校。"
    if score >= 560:
        return 60, "成绩处于稳妥区间，推荐层次匹配且特色明确的高校。"
    return 999, "成绩仅作参考，建议重点关注特色院校与招生材料匹配度。"


def _timeline(db: Session, university_id: int) -> str:
    rows = db.query(AdmissionSchedule).filter(AdmissionSchedule.university_id == university_id).order_by(AdmissionSchedule.month).all()
    return "；".join([f"{row.month}月：{row.registration_time}，材料截止{row.material_deadline}，{row.exam_time}" for row in rows[:3]])


def recommend_universities(db: Session, eligibility_type: str, intended_field: str = "", score: int | None = None, limit: int = 8) -> list[dict]:
    target = eligibility_type
    max_rank, score_reason = _score_band(score)
    field = (intended_field or "").strip()
    field_terms = FIELD_ALIASES.get(field, [field] if field else [])

    universities = db.query(University).filter(University.admission_targets.contains(target)).all()
    ranked = []
    for university in universities:
        field_match = not field_terms or any(term and term in (university.fields or "") for term in field_terms)
        if not field_match:
            continue
        tags = university.tags or ""
        level_bonus = -60 if "C9" in tags else -45 if "985" in tags else -28 if "纯211" in tags or "211" in tags else -10 if "双一流" in tags else 0
        international_bonus = -15 if eligibility_type == "international" and "支持国际生招生" in tags else 0
        huaqiao_bonus = -5 if eligibility_type == "huaqiao" and "支持华侨生招生" in tags else 0
        rank_bonus = 0 if university.ranking <= max_rank else 18
        specialty_bonus = -12 if field and field in (university.fields or "") else 0
        score_value = university.ranking + rank_bonus + level_bonus + international_bonus + huaqiao_bonus + specialty_bonus
        ranked.append((score_value, university))

    if not ranked and field:
        universities = db.query(University).filter(University.admission_targets.contains(target)).order_by(University.ranking).limit(limit).all()
        ranked = [(university.ranking + 30, university) for university in universities]

    ranked.sort(key=lambda item: item[0])
    results = []
    for _, university in ranked[:limit]:
        reason_parts = [score_reason]
        if field and field in (university.fields or ""):
            reason_parts.append(f"专业领域匹配“{field}”。")
        if eligibility_type == "huaqiao":
            reason_parts.append("该校支持华侨生相关招生通道。")
        else:
            reason_parts.append("该校支持国际生相关招生通道。")
        results.append({
            "id": university.id,
            "name": university.name,
            "ranking": university.ranking,
            "province": university.province,
            "tags": university.tags,
            "fields": university.fields,
            "advantage_majors": university.advantage_majors,
            "admission_timeline": _timeline(db, university.id),
            "official_url": university.official_url,
            "admission_url": university.admission_url,
            "admission_email": university.admission_email,
            "admission_phone": university.admission_phone,
            "admissions_office": university.admissions_office,
            "match_reason": " ".join(reason_parts),
        })
    return results
