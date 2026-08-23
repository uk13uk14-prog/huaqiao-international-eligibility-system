from sqlalchemy.orm import Session
from ..models import AdmissionSchedule, University
from .permissions import entitlements


def timeline(db: Session, uid: int):
    rows = db.query(AdmissionSchedule).filter(AdmissionSchedule.university_id == uid).order_by(AdmissionSchedule.month).limit(3).all()
    return "；".join([f"{r.month}月：{r.registration_time}，材料截止{r.material_deadline}，{r.exam_time}" for r in rows])


def recommend(db: Session, user, target: str, field: str = "综合", score: int | None = None):
    e = entitlements(user)
    q = db.query(University).filter(University.admission_targets.contains(target))
    if e["university_limit"] < 999:
        q = q.filter(University.is_core == False)
    schools = q.all()
    ranked = []
    for u in schools:
        tags = u.tags or ""
        level_bonus = -60 if "C9" in tags else -45 if "985" in tags else -28 if "纯211" in tags or "211" in tags else -10 if "双一流" in tags else 0
        international_bonus = -15 if target == "international" and "支持国际生招生" in tags else 0
        huaqiao_bonus = -5 if target == "huaqiao" and "支持华侨生招生" in tags else 0
        match = 0 if not field or field in (u.fields or "") else 30
        score_bonus = 0
        if score and score >= 650 and u.ranking <= 20:
            score_bonus = -12
        if score and score < 560 and u.ranking <= 20:
            score_bonus = 20
        ranked.append((u.ranking + match + score_bonus + level_bonus + international_bonus + huaqiao_bonus, u))
    ranked.sort(key=lambda x: x[0])
    out = []
    for _, u in ranked[:e["recommend_limit"]]:
        out.append({"id": u.id, "name": u.name, "ranking": u.ranking, "province": u.province, "tags": u.tags, "fields": u.fields, "advantage_majors": u.advantage_majors, "admission_timeline": timeline(db, u.id), "official_url": u.official_url, "admission_url": u.admission_url, "admission_email": u.admission_email, "admission_phone": u.admission_phone, "admissions_office": u.admissions_office, "locked": False, "match_reason": f"优先匹配招收国际生的C9/985/纯211层级，并结合{target}路径、{field}方向与当前会员权益。"})
    return out
