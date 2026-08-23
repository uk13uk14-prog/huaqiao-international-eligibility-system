import json
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db, init_db, SessionLocal
from .deps import verify_admin
from .models import AdmissionSchedule, AppClient, ConsultationRequest, EligibilityRecord, University, UserInfo
from .schemas import (
    AdminOverview,
    ConsultationCreate,
    ConsultationOut,
    ConsultationPatch,
    EligibilityInput,
    EligibilityResult,
    LawArticle,
    RecommendationOut,
    ScheduleOut,
    TelemetrySessionIn,
    UniversityOut,
)
from .seed import seed_data
from .services.nationality_law import NATIONALITY_LAW, get_article
from .services.policies import list_policy_documents
from .services.recommend import recommend_universities
from .services.rules import determine_huaqiao, determine_international, to_payload

settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0", description="华侨生/国际生资格智能判定 API")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.on_event("startup")
def startup():
    init_db()
    db = SessionLocal()
    try:
        seed_data(db)
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name}


@app.post("/api/telemetry/session")
def telemetry_session(payload: TelemetrySessionIn, request: Request, db: Session = Depends(get_db)):
    """客户端每次打开应用可调用一次，用于统计独立使用人数与打开次数。"""
    ua = (request.headers.get("user-agent") or "")[:500]
    cid = payload.client_id.strip()
    now = datetime.utcnow()
    row = db.query(AppClient).filter(AppClient.client_uuid == cid).first()
    if not row:
        db.add(
            AppClient(
                client_uuid=cid,
                first_seen_at=now,
                last_seen_at=now,
                ping_count=1,
                app_version=(payload.app_version or "")[:40],
                platform=(payload.platform or "")[:40],
                user_agent=ua,
            )
        )
    else:
        row.last_seen_at = now
        row.ping_count = (row.ping_count or 0) + 1
        if payload.app_version:
            row.app_version = (payload.app_version or "")[:40]
        if payload.platform:
            row.platform = (payload.platform or "")[:40]
        if ua:
            row.user_agent = ua
    db.commit()
    return {"ok": True}


@app.post("/api/consultation", response_model=ConsultationOut)
def create_consultation(payload: ConsultationCreate, db: Session = Depends(get_db)):
    row = ConsultationRequest(
        client_uuid=(payload.client_id or "")[:64],
        name=(payload.name or "")[:80],
        phone=(payload.phone or "")[:40],
        email=(payload.email or "")[:160],
        wechat=(payload.wechat or "")[:80],
        note=payload.note or "",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.get("/api/admin/overview", response_model=AdminOverview)
def admin_overview(_: bool = Depends(verify_admin), db: Session = Depends(get_db)):
    unique_clients = int(db.query(func.count(AppClient.id)).scalar() or 0)
    total_pings = int(db.query(func.coalesce(func.sum(AppClient.ping_count), 0)).scalar() or 0)
    consultation_total = db.query(ConsultationRequest).count()
    consultation_pending = db.query(ConsultationRequest).filter(ConsultationRequest.status == "pending").count()
    judgments = db.query(EligibilityRecord).count()
    return AdminOverview(
        unique_clients=unique_clients,
        total_client_pings=total_pings,
        consultation_requests_total=consultation_total,
        consultation_pending=consultation_pending,
        eligibility_judgments_total=judgments,
    )


@app.get("/api/admin/consultations", response_model=list[ConsultationOut])
def admin_list_consultations(
    status: str = Query("", description="pending / contacted / closed，空为全部"),
    limit: int = Query(200, ge=1, le=500),
    _: bool = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    q = db.query(ConsultationRequest).order_by(ConsultationRequest.created_at.desc())
    if status.strip():
        q = q.filter(ConsultationRequest.status == status.strip())
    return q.limit(limit).all()


@app.patch("/api/admin/consultations/{rid}", response_model=ConsultationOut)
def admin_patch_consultation(
    rid: int,
    patch: ConsultationPatch,
    _: bool = Depends(verify_admin),
    db: Session = Depends(get_db),
):
    row = db.query(ConsultationRequest).filter(ConsultationRequest.id == rid).first()
    if not row:
        raise HTTPException(status_code=404, detail="记录不存在")
    if patch.status is not None:
        if patch.status not in ("pending", "contacted", "closed"):
            raise HTTPException(status_code=422, detail="status 须为 pending、contacted 或 closed")
        row.status = patch.status
    if patch.admin_note is not None:
        row.admin_note = patch.admin_note
    db.commit()
    db.refresh(row)
    return row


@app.get("/admin")
def admin_dashboard():
    path = STATIC_DIR / "admin.html"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="未找到后台页面 static/admin.html")
    return FileResponse(path)


@app.get("/api/laws", response_model=list[LawArticle])
def list_laws(keyword: str = ""):
    if not keyword:
        return NATIONALITY_LAW
    return [item for item in NATIONALITY_LAW if keyword in item["text"] or keyword in item["title"] or keyword in item["explanation"]]


@app.get("/api/laws/{number}", response_model=LawArticle)
def law_detail(number: int):
    article = get_article(number)
    if not article:
        raise HTTPException(status_code=404, detail="条款不存在")
    return article


@app.get("/api/policies")
def policies(keyword: str = ""):
    return list_policy_documents(keyword)


def persist_result(db: Session, kind: str, data: EligibilityInput, result):
    user = UserInfo(
        name=data.name,
        birth_date=data.birth_date,
        current_nationality=data.current_nationality,
        has_chinese_nationality=data.has_chinese_nationality,
        has_foreign_nationality=data.has_foreign_nationality,
        passport_info=data.passport_info,
        household_info=data.household_info,
        residence_records=json.dumps({
            "settled_abroad": data.settled_abroad,
            "permanent_residence_country": data.permanent_residence_country,
            "overseas_residence_months_last_2y": data.overseas_residence_months_last_2y,
            "overseas_residence_months_last_4y": data.overseas_residence_months_last_4y,
            "annual_months_overseas": data.annual_months_overseas,
        }, ensure_ascii=False),
        family_info=json.dumps({
            "parent_chinese_citizen": data.parent_chinese_citizen,
            "parent_settled_abroad_at_birth": data.parent_settled_abroad_at_birth,
            "born_abroad": data.born_abroad,
        }, ensure_ascii=False),
    )
    db.add(user)
    db.flush()
    record = EligibilityRecord(
        user_id=user.id,
        eligibility_type=kind,
        qualified=result.qualified,
        conclusion=result.conclusion,
        reasons=json.dumps(result.reasons, ensure_ascii=False),
        basis_articles=json.dumps(result.article_numbers, ensure_ascii=False),
        suggestions=json.dumps(result.suggestions, ensure_ascii=False),
        raw_input=data.model_dump_json(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    recommendations = recommend_universities(db, kind, data.intended_field, data.score)
    return to_payload(record.id, user.id, kind, result, record.created_at, recommendations)


@app.post("/api/eligibility/huaqiao", response_model=EligibilityResult)
def judge_huaqiao(data: EligibilityInput, db: Session = Depends(get_db)):
    return persist_result(db, "huaqiao", data, determine_huaqiao(data))


@app.post("/api/eligibility/international", response_model=EligibilityResult)
def judge_international(data: EligibilityInput, db: Session = Depends(get_db)):
    return persist_result(db, "international", data, determine_international(data))


@app.get("/api/records", response_model=list[EligibilityResult])
def records(kind: str = Query("", pattern="^(|huaqiao|international)$"), db: Session = Depends(get_db)):
    query = db.query(EligibilityRecord).order_by(EligibilityRecord.created_at.desc())
    if kind:
        query = query.filter(EligibilityRecord.eligibility_type == kind)
    items = []
    for record in query.limit(200).all():
        rr = type("Result", (), {})()
        rr.qualified = record.qualified
        rr.conclusion = record.conclusion
        rr.reasons = json.loads(record.reasons)
        rr.article_numbers = json.loads(record.basis_articles)
        rr.suggestions = json.loads(record.suggestions or "[]")
        items.append(to_payload(record.id, record.user_id, record.eligibility_type, rr, record.created_at))
    return items


@app.get("/api/universities", response_model=list[UniversityOut])
def universities(target: str = Query("", pattern="^(|huaqiao|international)$"), keyword: str = "", field: str = "", province: str = "", tag: str = "", feature: str = "", db: Session = Depends(get_db)):
    query = db.query(University)
    if target:
        query = query.filter(University.admission_targets.contains(target))
    if field:
        query = query.filter(University.fields.contains(field))
    if keyword:
        query = query.filter(University.name.contains(keyword))
    if province:
        query = query.filter(University.province == province)
    if tag:
        if tag == "211":
            query = query.filter((University.tags.contains("211")) | (University.tags.contains("纯211")))
        else:
            query = query.filter(University.tags.contains(tag))
    if feature:
        if feature == "艺术":
            query = query.filter((University.fields.contains("音乐")) | (University.fields.contains("美术")) | (University.fields.contains("设计")) | (University.university_type.contains("艺术")))
        elif feature == "师范":
            query = query.filter((University.university_type.contains("师范")) | (University.name.contains("师范")))
        else:
            query = query.filter(University.fields.contains(feature))
    return query.order_by(University.ranking, University.name).all()


@app.get("/api/schedules", response_model=list[ScheduleOut])
def schedules(target: str = Query("", pattern="^(|huaqiao|international)$"), month: int | None = None, field: str = "", province: str = "", tag: str = "", feature: str = "", db: Session = Depends(get_db)):
    query = db.query(AdmissionSchedule, University).join(University, AdmissionSchedule.university_id == University.id)
    if target:
        query = query.filter(University.admission_targets.contains(target))
    if field:
        query = query.filter(University.fields.contains(field))
    if month:
        query = query.filter(AdmissionSchedule.month == month)
    if province:
        query = query.filter(University.province == province)
    if tag:
        if tag == "211":
            query = query.filter((University.tags.contains("211")) | (University.tags.contains("纯211")))
        else:
            query = query.filter(University.tags.contains(tag))
    if feature:
        if feature == "艺术":
            query = query.filter((University.fields.contains("音乐")) | (University.fields.contains("美术")) | (University.fields.contains("设计")) | (University.university_type.contains("艺术")))
        elif feature == "师范":
            query = query.filter((University.university_type.contains("师范")) | (University.name.contains("师范")))
        else:
            query = query.filter(University.fields.contains(feature))
    rows = query.order_by(AdmissionSchedule.year, AdmissionSchedule.month, University.ranking).all()
    return [ScheduleOut(id=s.id, university_id=u.id, university_name=u.name, target=u.target, ranking=u.ranking, province=u.province, tags=u.tags, fields=u.fields, year=s.year, month=s.month, registration_time=s.registration_time, material_deadline=s.material_deadline, exam_time=s.exam_time, reminder=s.reminder) for s, u in rows]


@app.get("/api/recommendations", response_model=list[RecommendationOut])
def recommendations(
    target: str = Query(..., pattern="^(huaqiao|international)$"),
    intended_field: str = "",
    score: int | None = None,
    db: Session = Depends(get_db),
):
    return recommend_universities(db, target, intended_field, score)

