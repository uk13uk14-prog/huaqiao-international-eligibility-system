from sqlalchemy import text
from sqlalchemy.orm import Session

from .models import AdmissionSchedule, University
from .services.university_catalog import DEFAULT_SCHEDULES, FIELD_SCHEDULES, UNIVERSITIES

# 与 SaaS Pro seed 一致的免费增补院校（非 985/211 主库）
FREE_UNIVERSITIES = [
    {
        "ranking": 901,
        "name": "深圳大学",
        "province": "广东",
        "university_type": "综合类",
        "tags": "双非,支持国际生招生,支持华侨生招生,免费可查,非核心院校",
        "fields": "综合,理工,文史,设计",
        "advantage_majors": "计算机、电子信息、建筑学、设计学、经济管理",
        "url": "https://www.szu.edu.cn/",
    },
    {
        "ranking": 902,
        "name": "南方科技大学",
        "province": "广东",
        "university_type": "理工类",
        "tags": "双非,支持国际生招生,支持华侨生招生,免费可查,非核心院校",
        "fields": "理工,综合",
        "advantage_majors": "数学、物理、材料、电子信息、计算机",
        "url": "https://www.sustech.edu.cn/",
    },
    {
        "ranking": 903,
        "name": "首都师范大学",
        "province": "北京",
        "university_type": "师范类/综合",
        "tags": "双一流,支持国际生招生,支持华侨生招生,免费可查,非核心院校",
        "fields": "综合,文史,美术,音乐",
        "advantage_majors": "教育学、中文、历史学、美术、音乐教育",
        "url": "https://www.cnu.edu.cn/",
    },
]

LEGACY_FREE_REPLACEMENTS = {
    "区域国际本科示范学院": {
        "ranking": 904,
        "name": "宁波大学",
        "province": "浙江",
        "university_type": "综合类",
        "tags": "双一流,支持国际生招生,支持华侨生招生,免费可查,非核心院校",
        "fields": "综合,理工,文史",
        "advantage_majors": "水产、力学、信息科学、国际经济与贸易、法学",
        "url": "https://www.nbu.edu.cn/",
    },
    "国际艺术预科学院": {
        "ranking": 905,
        "name": "南京艺术学院",
        "province": "江苏",
        "university_type": "艺术类",
        "tags": "双非,支持国际生招生,支持华侨生招生,免费可查,非核心院校",
        "fields": "音乐,美术,设计",
        "advantage_majors": "音乐表演、美术学、设计学、传媒艺术、舞蹈",
        "url": "https://www.nua.edu.cn/",
    },
    "国际体育教育学院": {
        "ranking": 906,
        "name": "成都体育学院",
        "province": "四川",
        "university_type": "体育类",
        "tags": "双非,支持国际生招生,支持华侨生招生,免费可查,非核心院校",
        "fields": "体育",
        "advantage_majors": "体育教育、运动训练、运动康复、武术与民族传统体育",
        "url": "https://www.cdsu.edu.cn/",
    },
}


def ensure_university_columns(db: Session):
    """Check and add missing columns using SQLAlchemy inspector (PostgreSQL compatible)."""
    from sqlalchemy import inspect
    inspector = inspect(db.get_bind())
    existing = {col["name"] for col in inspector.get_columns("universities")}
    # Columns are now managed by Alembic migrations
    # This function is kept for backward compatibility but does nothing


def schedules_for(fields: str):
    rows = list(DEFAULT_SCHEDULES)
    for key, schedules in FIELD_SCHEDULES.items():
        if key in fields:
            rows.extend(schedules)
    return rows


def contact_for(item: dict):
    admission_url = item.get("admission_url") or item["url"]
    return {
        "admission_url": admission_url,
        "admission_email": item.get("email") or "",
        "admission_phone": item.get("phone") or "",
        "admissions_office": item.get("office") or "",
    }


def upsert_university(db: Session, item: dict):
    university = db.query(University).filter(University.name == item["name"]).first()
    if not university:
        university = University(name=item["name"], target="both")
        db.add(university)
        db.flush()
    contact = contact_for(item)
    university.ranking = item["ranking"]
    university.province = item["province"]
    university.university_type = item.get("university_type", "")
    university.target = "both"
    university.admission_targets = "international,huaqiao"
    university.tags = item["tags"]
    university.fields = item["fields"]
    university.advantage_majors = item["advantage_majors"]
    university.description = item.get("description") or (
        f"{item['name']}是{item['province']}重点院校，覆盖{item['fields']}等国际生与华侨生咨询方向。"
    )
    university.requirements = item.get("requirements") or "按当年官方招生简章提交身份、学历、成绩、语言、作品集或专项证明等材料。"
    university.official_url = item["url"]
    university.admission_url = contact["admission_url"]
    university.admission_email = contact["admission_email"]
    university.admission_phone = contact["admission_phone"]
    university.admissions_office = contact["admissions_office"]
    db.query(AdmissionSchedule).filter(AdmissionSchedule.university_id == university.id).delete()
    for year, month, reg, deadline, exam, reminder in schedules_for(item["fields"]):
        db.add(
            AdmissionSchedule(
                university_id=university.id,
                year=year,
                month=month,
                registration_time=reg,
                material_deadline=deadline,
                exam_time=exam,
                reminder=reminder,
            )
        )


def seed_data(db: Session):
    ensure_university_columns(db)
    for item in UNIVERSITIES:
        upsert_university(db, item)
    for old_name, item in LEGACY_FREE_REPLACEMENTS.items():
        legacy = db.query(University).filter(University.name == old_name).first()
        if legacy and not db.query(University).filter(University.name == item["name"]).first():
            legacy.name = item["name"]
            db.flush()
        if legacy:
            upsert_university(db, item)
    for item in FREE_UNIVERSITIES:
        upsert_university(db, item)
    db.commit()
