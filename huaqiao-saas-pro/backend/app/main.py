import json
import logging
import secrets
import time
from datetime import datetime, timedelta

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from .config import get_settings
from .database import SessionLocal, get_db, init_db
from .models import (
    AdmissionSchedule,
    ConsultationReportVersion,
    CustomerVault,
    EligibilityRecord,
    ExpertConsultation,
    MemberTimelineReminder,
    MembershipPlan,
    Order,
    PaymentOrder,
    RechargeCode,
    Tenant,
    University,
    User,
)
from .schemas import (
    AdminExpertConsultationPatch,
    AdminReminderCreate,
    AdminReminderPatch,
    CreateCodeIn,
    CreatePaymentIn,
    CustomerVaultUpsert,
    EligibilityInput,
    ExpertConsultationCreate,
    LoginIn,
    RedeemIn,
    RegisterIn,
)
from .seed import seed_data
from .services.expert_tasks import run_expert_ai_draft
from .services.law import NATIONALITY_LAW
from .services.permissions import FREE_LIMITS, entitlements, feature_summary
from .services.payments import create_payment_order, mark_payment_paid
from .services.planning import planning_for
from .services.policies import list_policy_documents
from .services.recommend import recommend
from .services.eligibility_engine import evaluate_international_student, evaluate_overseas_chinese_student, InternationalStudentInput, OverseasChineseStudentInput
from .services.rules import judge_huaqiao, judge_international  # DEPRECATED: kept for backward compat, not used for final policy decision
from .services.eligibility_engine import evaluate_overseas_chinese_student, evaluate_international_student
from .services.security import create_token, get_current_user, get_current_user_optional, hash_password, is_paid, require_admin, verify_password
from .services.vault_crypto import decrypt_profile_json, encrypt_profile_json
from .services.privacy import redact_log_message, AuditLogger, AuditAction

logger = logging.getLogger(__name__)
settings = get_settings()

# Audit logger instance
audit_logger = AuditLogger()

app = FastAPI(title=settings.app_name, version="1.0.0", description="国际生资格智评系统 SaaS Pro API")

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


# --- Log Redaction & Privacy Audit Middleware ---
@app.middleware("http")
async def privacy_audit_middleware(request: Request, call_next):
    """Middleware that redacts sensitive data from request logs and audits admin access."""
    start_time = time.time()
    path = request.url.path
    method = request.method
    client_ip = request.client.host if request.client else "unknown"

    # Log request (redacted)
    try:
        body_bytes = await request.body()
        if body_bytes:
            body_text = body_bytes.decode("utf-8", errors="replace")[:500]
            redacted_body = redact_log_message(body_text)
            logger.info(f"Request: {method} {path} from {client_ip} body={redacted_body}")
    except Exception:
        logger.info(f"Request: {method} {path} from {client_ip}")

    response = await call_next(request)

    duration_ms = round((time.time() - start_time) * 1000, 1)
    logger.info(f"Response: {method} {path} status={response.status_code} duration={duration_ms}ms")

    # Audit log for admin endpoints
    if path.startswith("/api/admin/") and response.status_code == 200:
        audit_logger.log(
            actor=client_ip,
            action=AuditAction.ADMIN_ACCESS_PROFILE,
            resource_type="admin_endpoint",
            resource_id=path,
            details={"method": method, "status": response.status_code},
        )

    return response


@app.on_event("startup")
def startup():
    # Validate required production settings
    if not settings.jwt_secret_key or settings.jwt_secret_key == "change-me-in-production":
        raise RuntimeError("JWT_SECRET_KEY must be set. Generate with: python -c 'import secrets; print(secrets.token_urlsafe(48))'")
    from .services.vault_crypto import validate_vault_config
    validate_vault_config()
    init_db()
    db = SessionLocal()
    try:
        seed_data(db)
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name}


def user_payload(user: User):
    fs = feature_summary(user)
    return {"id": user.id, "tenant_id": user.tenant_id, "email": user.email, "name": user.name, "role": user.role, "plan_code": user.plan_code, "membership_until": user.membership_until.isoformat() if user.membership_until else None, "paid": fs["paid"], "features": fs}


@app.post("/api/auth/register")
@limiter.limit("5/minute")
def register(request: Request, data: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="邮箱已注册")
    tenant = Tenant(name=data.tenant_name, tenant_type=data.tenant_type)
    db.add(tenant); db.flush()
    user = User(tenant_id=tenant.id, email=data.email, name=data.name or data.email, password_hash=hash_password(data.password), role="member", plan_code="free")
    db.add(user); db.commit(); db.refresh(user)
    token = create_token(db, user)
    return {"token": token, "user": user_payload(user)}


@app.post("/api/auth/login")
@limiter.limit("10/minute")
def login(request: Request, data: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=401, detail="账号或密码错误")
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="账号或密码错误")
    # Legacy SHA256 migration: if hash doesn't start with $2b$, it's old format
    if not user.password_hash.startswith("$2b$"):
        if _legacy_verify_password(data.password, user.password_hash):
            user.password_hash = hash_password(data.password)
            db.commit()
        else:
            raise HTTPException(status_code=401, detail="账号或密码错误")
    return {"token": create_token(db, user), "user": user_payload(user)}


@app.get("/api/me")
def me(user: User = Depends(get_current_user)):
    return user_payload(user)


@app.get("/api/plans")
def plans(db: Session = Depends(get_db)):
    return db.query(MembershipPlan).filter(MembershipPlan.is_active == True).all()


@app.post("/api/billing/redeem")
def redeem(data: RedeemIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    code = db.query(RechargeCode).filter(RechargeCode.code == data.code, RechargeCode.is_used == False).first()
    if not code:
        raise HTTPException(status_code=400, detail="卡密无效或已使用")
    user.plan_code = code.plan_code
    base = datetime.utcnow() if not user.membership_until or user.membership_until < datetime.utcnow() else user.membership_until
    user.membership_until = base + timedelta(days=code.duration_days)
    if code.plan_code == "lifetime":
        user.membership_until = datetime.utcnow() + timedelta(days=36500)
    code.is_used = True; code.used_by = user.id; code.used_at = datetime.utcnow()
    db.add(Order(tenant_id=user.tenant_id, user_id=user.id, plan_code=code.plan_code, amount=0, status="paid", source="recharge_code"))
    db.commit(); db.refresh(user)
    return {"message": "开通成功", "user": user_payload(user)}


@app.get("/api/billing/orders")
def orders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Order).filter(Order.tenant_id == user.tenant_id).order_by(Order.created_at.desc()).all()


@app.post("/api/payments/create")
def create_payment(data: CreatePaymentIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        payment, plan = create_payment_order(db, user, data.plan_code, data.channel)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "order_no": payment.order_no,
        "plan_code": plan.code,
        "plan_name": plan.name,
        "channel": payment.channel,
        "amount": payment.amount,
        "status": payment.status,
        "pay_url": payment.pay_url,
        "qr_content": payment.qr_content,
        "message": "微信/支付宝正式上线前，请在后台配置商户证书与验签；本地可使用 mock 支付完成测试。",
    }


@app.get("/api/payments/{order_no}")
def payment_status(order_no: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    payment = db.query(PaymentOrder).filter(PaymentOrder.order_no == order_no, PaymentOrder.tenant_id == user.tenant_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="支付订单不存在")
    return {"order_no": payment.order_no, "plan_code": payment.plan_code, "channel": payment.channel, "amount": payment.amount, "status": payment.status, "paid_at": payment.paid_at}


@app.post("/api/payments/mock/{order_no}/pay")
def mock_pay(order_no: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    payment = db.query(PaymentOrder).filter(PaymentOrder.order_no == order_no, PaymentOrder.tenant_id == user.tenant_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="支付订单不存在")
    if payment.channel != "mock":
        raise HTTPException(status_code=400, detail="该订单不是模拟支付订单")
    try:
        paid = mark_payment_paid(db, order_no, provider_trade_no=f"MOCK-{order_no}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.refresh(user)
    return {"message": "模拟支付成功，会员已自动开通", "payment": {"order_no": paid.order_no, "status": paid.status}, "user": user_payload(user)}


@app.post("/api/payments/notify/wechat")
async def wechat_notify(request: Request, db: Session = Depends(get_db)):
    from .services.payment_verify import verify_wechat_callback
    settings = get_settings()
    body = await request.body()
    try:
        order_no, amount, provider_trade_no = verify_wechat_callback(
            body=body,
            headers=dict(request.headers),
            mch_id=settings.wechat_pay_mch_id,
            api_v3_key=settings.wechat_pay_api_v3_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        paid = mark_payment_paid(db, order_no, provider_trade_no=provider_trade_no)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"code": "SUCCESS", "message": "成功", "order_no": paid.order_no}


@app.post("/api/payments/notify/alipay")
async def alipay_notify(request: Request, db: Session = Depends(get_db)):
    from .services.payment_verify import verify_alipay_callback
    settings = get_settings()
    body = await request.body()
    form_data = {}
    try:
        form_data = dict(await request.form())
    except Exception:
        pass
    try:
        order_no, amount, provider_trade_no = verify_alipay_callback(
            form_data=form_data,
            alipay_public_key=settings.alipay_public_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        paid = mark_payment_paid(db, order_no, provider_trade_no=provider_trade_no)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "order_no": paid.order_no}


@app.get("/api/laws")
def laws(keyword: str = ""):
    if not keyword:
        return NATIONALITY_LAW
    return [item for item in NATIONALITY_LAW if keyword in item["text"] or keyword in item["title"] or keyword in item["explanation"]]


@app.get("/api/policies")
def policies(keyword: str = ""):
    return list_policy_documents(keyword)


def paid_planning_payload(_user: User, kind: str):
    """规划时间线与材料清单对所有登录用户开放；一对一深度方案通过前端「规划咨询」联系顾问。"""
    return {"locked": False, **planning_for(kind)}


@app.get("/api/planning/{kind}")
def planning(kind: str, user: User = Depends(get_current_user)):
    if kind not in {"international", "huaqiao"}:
        raise HTTPException(status_code=400, detail="规划类型不支持")
    return paid_planning_payload(user, kind)


@app.post("/api/eligibility/international")
@limiter.limit("10/minute")
def international(request: Request, data: EligibilityInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    engine_input = InternationalStudentInput(
        has_foreign_nationality=data.has_foreign_nationality,
        foreign_nationality_country=data.foreign_nationality_country,
        passport_issue_date=data.passport_issue_date,
        birth_country=data.birth_country,
        birth_at_foreign_nationality=data.birth_at_foreign_nationality,
        parent_chinese_citizen=data.parent_chinese_citizen,
        parent_settled_abroad=data.parent_settled_abroad,
        previous_chinese_nationality=data.previous_chinese_nationality,
        naturalization_date=data.naturalization_date,
        denationalization_certificate=data.denationalization_certificate,
        intended_admission_year=data.intended_admission_year or 2026,
        overseas_residence_months_last_4y=data.overseas_residence_months_last_4y,
        annual_months_overseas=data.annual_months_overseas,
    )
    result = evaluate_international_student(engine_input)
    recs = recommend(db, user, "international", data.intended_field, data.score)
    # R4.3 FIX: Encrypt raw_input before persistence
    from .services.encryption_at_rest import encrypt_json, encrypt_text, blind_index
    raw_input_enc = encrypt_json(data.model_dump())
    passport_plain = getattr(data, "passport_number", "") or ""
    passport_idx = blind_index(passport_plain) if passport_plain else ""
    record = EligibilityRecord(tenant_id=user.tenant_id, user_id=user.id, eligibility_type="international", qualified=result["result"] == "PRELIMINARY_ELIGIBLE", conclusion=result["explanation"], reasons=json.dumps(result.get("failed_rules", []), ensure_ascii=False), basis_articles=json.dumps(result.get("evidence", []), ensure_ascii=False), suggestions=json.dumps(result.get("manual_review_rules", []), ensure_ascii=False), recommendations=json.dumps(recs, ensure_ascii=False), raw_input="[ENCRYPTED]", raw_input_encrypted=raw_input_enc, passport_blind_index=passport_idx)
    db.add(record); db.commit(); db.refresh(record)
    return {**result, "record_id": record.id, "recommendations": recs, "planning": paid_planning_payload(user, "international"), "features": feature_summary(user)}


@app.post("/api/eligibility/huaqiao")
@limiter.limit("10/minute")
def huaqiao(request: Request, data: EligibilityInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    engine_input = OverseasChineseStudentInput(
        has_chinese_nationality=data.has_chinese_nationality,
        has_foreign_nationality=data.has_foreign_nationality,
        has_mainland_household=data.has_mainland_household,
        has_hkmt_household=data.has_hkmt_household,
        residence_type=data.residence_type,
        residence_country=data.residence_country,
        residence_years=data.residence_years,
        overseas_residence_months_last_2y=data.overseas_residence_months_last_2y,
        overseas_residence_months_last_5y=data.overseas_residence_months_last_5y,
        parent_residence_months_last_2y=data.parent_residence_months_last_2y,
        parent_residence_months_last_5y=data.parent_residence_months_last_5y,
        intended_admission_year=data.intended_admission_year or 2026,
    )
    result = evaluate_overseas_chinese_student(engine_input)
    recs = recommend(db, user, "huaqiao", data.intended_field, data.score)
    # R4.3 FIX: Encrypt raw_input before persistence
    from .services.encryption_at_rest import encrypt_json, blind_index
    raw_input_enc = encrypt_json(data.model_dump())
    id_card_plain = getattr(data, "id_card_number", "") or ""
    id_card_idx = blind_index(id_card_plain) if id_card_plain else ""
    record = EligibilityRecord(tenant_id=user.tenant_id, user_id=user.id, eligibility_type="huaqiao", qualified=result["result"] == "PRELIMINARY_ELIGIBLE", conclusion=result["explanation"], reasons=json.dumps(result.get("failed_rules", []), ensure_ascii=False), basis_articles=json.dumps(result.get("evidence", []), ensure_ascii=False), suggestions=json.dumps(result.get("manual_review_rules", []), ensure_ascii=False), recommendations=json.dumps(recs, ensure_ascii=False), raw_input="[ENCRYPTED]", raw_input_encrypted=raw_input_enc, id_card_blind_index=id_card_idx)
    db.add(record); db.commit(); db.refresh(record)
    return {**result, "record_id": record.id, "recommendations": recs, "planning": paid_planning_payload(user, "huaqiao"), "features": feature_summary(user)}


@app.get("/api/records")
def records(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    limit = entitlements(user)["record_limit"]
    rows = db.query(EligibilityRecord).filter(EligibilityRecord.tenant_id == user.tenant_id).order_by(EligibilityRecord.created_at.desc()).limit(limit).all()
    # R4.3 FIX 6: Return masked records — no sensitive fields
    return [{"id": r.id, "type": r.eligibility_type, "qualified": r.qualified, "conclusion": r.conclusion, "created_at": r.created_at} for r in rows]


@app.get("/api/records/{record_id}")
def record_detail(record_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    record = db.query(EligibilityRecord).filter(EligibilityRecord.id == record_id, EligibilityRecord.tenant_id == user.tenant_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {
        "id": record.id,
        "type": record.eligibility_type,
        "qualified": record.qualified,
        "conclusion": record.conclusion,
        "reasons": json.loads(record.reasons or "[]"),
        "basis_articles": json.loads(record.basis_articles or "[]"),
        "suggestions": json.loads(record.suggestions or "[]"),
        "recommendations": json.loads(record.recommendations or "[]"),
        "planning": paid_planning_payload(user, record.eligibility_type),
        "raw_input": "[MASKED]",
        "created_at": record.created_at,
    }


@app.get("/api/records/{record_id}/report", response_class=PlainTextResponse)
def export_report(record_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not feature_summary(user).get("custom_expert_report"):
        raise HTTPException(status_code=402, detail="开通会员后可导出定制专家报告/正式判定报告")
    record = db.query(EligibilityRecord).filter(EligibilityRecord.id == record_id, EligibilityRecord.tenant_id == user.tenant_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    reasons = json.loads(record.reasons or "[]")
    articles = json.loads(record.basis_articles or "[]")
    recs = json.loads(record.recommendations or "[]")
    lines = [
        "国际生资格智评系统 Pro 判定报告",
        "=" * 32,
        f"判定模块：{record.eligibility_type}",
        f"判定结论：{record.conclusion}",
        f"判定结果：{'合格' if record.qualified else '不合格'}",
        f"生成时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "一、判定理由",
        *[f"- {item}" for item in reasons],
        "",
        "二、国籍法依据",
        *[f"- 第{item.get('number')}条 {item.get('title')}：{item.get('text')}" for item in articles],
        "",
        "三、推荐大学",
        *[f"- #{item.get('ranking')} {item.get('name')}：{item.get('advantage_majors')}" for item in recs],
        "",
        "说明：本报告用于国际生升学规划参考，不替代学校或主管部门最终审核。",
    ]
    return "\n".join(lines)


@app.get("/api/universities")
def universities(
    target: str = Query("international"),
    field: str = "",
    province: str = "",
    tag: str = "",
    feature: str = "",
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    e = entitlements(user) if user else FREE_LIMITS
    q = db.query(University).filter(University.admission_targets.contains(target))
    if field:
        q = q.filter(University.fields.contains(field))
    if province:
        q = q.filter(University.province == province)
    if tag:
        if tag == "211":
            q = q.filter((University.tags.contains("211")) | (University.tags.contains("纯211")))
        else:
            q = q.filter(University.tags.contains(tag))
    if feature:
        if feature == "艺术":
            q = q.filter((University.fields.contains("音乐")) | (University.fields.contains("美术")) | (University.fields.contains("设计")) | (University.university_type.contains("艺术")))
        elif feature == "师范":
            q = q.filter((University.university_type.contains("师范")) | (University.name.contains("师范")))
        else:
            q = q.filter(University.fields.contains(feature))
    if e["university_limit"] < 999:
        q = q.filter(University.is_core == False)
    rows = q.order_by(University.ranking).limit(e["university_limit"]).all()
    return [{
        "id": u.id,
        "ranking": u.ranking,
        "name": u.name,
        "province": u.province,
        "university_type": u.university_type,
        "tags": u.tags,
        "fields": u.fields,
        "advantage_majors": u.advantage_majors,
        "description": u.description,
        "requirements": u.requirements,
        "official_url": u.official_url,
        "admission_url": u.admission_url,
        "admission_email": u.admission_email,
        "admission_phone": u.admission_phone,
        "admissions_office": u.admissions_office,
        "locked_notice": None if e["university_limit"] >= 999 else "升级会员解锁C9/985/211前50完整名校库",
    } for u in rows]


@app.get("/api/schedules")
def schedules(
    target: str = "international",
    month: int | None = None,
    province: str = "",
    tag: str = "",
    feature: str = "",
    user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    e = entitlements(user) if user else FREE_LIMITS
    q = db.query(University).filter(University.admission_targets.contains(target))
    if province:
        q = q.filter(University.province == province)
    if tag:
        if tag == "211":
            q = q.filter((University.tags.contains("211")) | (University.tags.contains("纯211")))
        else:
            q = q.filter(University.tags.contains(tag))
    if feature:
        if feature == "艺术":
            q = q.filter((University.fields.contains("音乐")) | (University.fields.contains("美术")) | (University.fields.contains("设计")) | (University.university_type.contains("艺术")))
        elif feature == "师范":
            q = q.filter((University.university_type.contains("师范")) | (University.name.contains("师范")))
        else:
            q = q.filter(University.fields.contains(feature))
    if e["university_limit"] < 999:
        q = q.filter(University.is_core == False)
    rows = q.order_by(University.ranking).limit(e["university_limit"] if e["university_limit"] < 999 else 80).all()
    items = []
    for u in rows:
        schedules_query = db.query(AdmissionSchedule).filter_by(university_id=u.id)
        if month:
            schedules_query = schedules_query.filter_by(month=month)
        for s in schedules_query.order_by(AdmissionSchedule.month).all():
            items.append({"university_name": u.name, "ranking": u.ranking, "province": u.province, "tags": u.tags, "fields": u.fields, "year": s.year, "month": s.month, "registration_time": s.registration_time, "material_deadline": s.material_deadline, "exam_time": s.exam_time, "reminder": s.reminder})
    return items


@app.get("/api/recommendations")
def recommendations(target: str = "international", field: str = "综合", score: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return recommend(db, user, target, field, score)


@app.get("/api/vault/profile")
def vault_get(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not is_paid(user):
        raise HTTPException(status_code=402, detail="请开通会员后使用云端客户资料库")
    row = db.query(CustomerVault).filter(CustomerVault.user_id == user.id).first()
    if not row or not row.cipher_blob:
        return {"profile": {}, "updated_at": None}
    try:
        return {"profile": decrypt_profile_json(row.cipher_blob), "updated_at": row.updated_at}
    except Exception:
        raise HTTPException(status_code=500, detail="资料解密失败，请联系管理员")


@app.put("/api/vault/profile")
def vault_put(payload: CustomerVaultUpsert, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not is_paid(user):
        raise HTTPException(status_code=402, detail="请开通会员后同步云端客户资料库")
    row = db.query(CustomerVault).filter(CustomerVault.user_id == user.id).first()
    blob = encrypt_profile_json(payload.profile or {})
    if not row:
        row = CustomerVault(user_id=user.id, tenant_id=user.tenant_id, cipher_blob=blob)
        db.add(row)
    else:
        row.cipher_blob = blob
    db.commit()
    db.refresh(row)
    return {"ok": True, "updated_at": row.updated_at}


@app.post("/api/expert/consultations")
async def expert_consult_create(
    payload: ExpertConsultationCreate,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not feature_summary(user).get("one_on_one_expert"):
        raise HTTPException(status_code=402, detail="一对一专家咨询仅对付费会员开放")
    row = ExpertConsultation(
        tenant_id=user.tenant_id,
        user_id=user.id,
        title=(payload.title or "")[:200],
        question=payload.question,
        personalization=payload.personalization or "",
        contact_phone=payload.contact_phone[:40],
        contact_email=payload.contact_email[:160],
        contact_wechat=payload.contact_wechat[:80],
        status="pending_ai",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    background_tasks.add_task(run_expert_ai_draft, row.id)
    return {"id": row.id, "status": row.status, "message": "已提交，系统将自动生成书面初稿供顾问审核"}


@app.get("/api/expert/consultations")
def expert_consult_list(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not is_paid(user):
        raise HTTPException(status_code=402, detail="请开通会员后查看咨询记录")
    rows = db.query(ExpertConsultation).filter(ExpertConsultation.user_id == user.id).order_by(ExpertConsultation.created_at.desc()).limit(100).all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "status": r.status,
            "created_at": r.created_at,
            "has_final": bool((r.final_report or "").strip()),
            "ai_ready": r.status in ("draft_ready", "in_review", "published", "archived"),
        }
        for r in rows
    ]


@app.get("/api/expert/consultations/{cid}")
def expert_consult_detail(cid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not is_paid(user):
        raise HTTPException(status_code=402, detail="请开通会员后查看")
    r = db.query(ExpertConsultation).filter(ExpertConsultation.id == cid, ExpertConsultation.user_id == user.id).first()
    if not r:
        raise HTTPException(status_code=404, detail="不存在")
    show_final = r.status == "published" and (r.final_report or "").strip()
    return {
        "id": r.id,
        "title": r.title,
        "question": r.question,
        "personalization": r.personalization,
        "status": r.status,
        "message": (
            "顾问正在审核书面初稿"
            if r.status in ("draft_ready", "in_review")
            else ("初稿生成中" if r.status == "pending_ai" else ("处理遇到问题，顾问将人工介入" if r.status == "ai_failed" else ""))
        ),
        "final_report": r.final_report if show_final else "",
        "published_at": r.published_at,
        "created_at": r.created_at,
    }


@app.get("/api/member/reminders")
def member_reminders(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not feature_summary(user).get("full_timeline_reminders"):
        raise HTTPException(status_code=402, detail="完整智能时间轴提醒适用于年会员/三年会员等")
    rows = (
        db.query(MemberTimelineReminder)
        .filter(MemberTimelineReminder.user_id == user.id)
        .order_by(MemberTimelineReminder.remind_at.asc())
        .limit(200)
        .all()
    )
    return [
        {
            "id": r.id,
            "title": r.title,
            "body": r.body,
            "remind_at": r.remind_at,
            "category": r.category,
            "status": r.status,
            "admin_note": r.admin_note,
        }
        for r in rows
    ]


@app.get("/api/admin/expert-consultations")
def admin_expert_list(user_id: int | None = None, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    q = db.query(ExpertConsultation).order_by(ExpertConsultation.created_at.desc())
    if user_id:
        q = q.filter(ExpertConsultation.user_id == user_id)
    rows = q.limit(300).all()
    return [
        {
            "id": r.id,
            "tenant_id": r.tenant_id,
            "user_id": r.user_id,
            "title": r.title,
            "status": r.status,
            "contact_phone": r.contact_phone,
            "contact_email": r.contact_email,
            "contact_wechat": r.contact_wechat,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        }
        for r in rows
    ]


@app.get("/api/admin/expert-consultations/{cid}")
def admin_expert_one(cid: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    r = db.query(ExpertConsultation).filter(ExpertConsultation.id == cid).first()
    if not r:
        raise HTTPException(status_code=404, detail="不存在")
    u = db.query(User).filter(User.id == r.user_id).first()
    versions = db.query(ConsultationReportVersion).filter(ConsultationReportVersion.consultation_id == cid).order_by(ConsultationReportVersion.version_no.asc()).all()
    return {
        "consultation": {
            "id": r.id,
            "tenant_id": r.tenant_id,
            "user_id": r.user_id,
            "title": r.title,
            "question": r.question,
            "personalization": r.personalization,
            "contact_phone": r.contact_phone,
            "contact_email": r.contact_email,
            "contact_wechat": r.contact_wechat,
            "status": r.status,
            "ai_draft": r.ai_draft,
            "ai_model": r.ai_model,
            "final_report": r.final_report,
            "admin_note": r.admin_note,
            "reviewed_by_user_id": r.reviewed_by_user_id,
            "published_at": r.published_at,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        },
        "user_email": u.email if u else "",
        "user_name": u.name if u else "",
        "versions": [
            {"id": v.id, "version_no": v.version_no, "content": v.content, "source": v.source, "editor_user_id": v.editor_user_id, "created_at": v.created_at}
            for v in versions
        ],
    }


@app.patch("/api/admin/expert-consultations/{cid}")
def admin_expert_patch(cid: int, patch: AdminExpertConsultationPatch, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    r = db.query(ExpertConsultation).filter(ExpertConsultation.id == cid).first()
    if not r:
        raise HTTPException(status_code=404, detail="不存在")
    if patch.status is not None:
        r.status = patch.status
        if patch.status == "published":
            r.published_at = datetime.utcnow()
            r.reviewed_by_user_id = admin.id
    if patch.final_report is not None:
        r.final_report = patch.final_report
        last = db.query(ConsultationReportVersion).filter(ConsultationReportVersion.consultation_id == r.id).order_by(ConsultationReportVersion.version_no.desc()).first()
        vn = (last.version_no + 1) if last else 1
        db.add(
            ConsultationReportVersion(
                consultation_id=r.id,
                version_no=vn,
                content=patch.final_report,
                source="admin_edit",
                editor_user_id=admin.id,
            )
        )
    if patch.admin_note is not None:
        r.admin_note = patch.admin_note
    db.commit()
    db.refresh(r)
    return {
        "id": r.id,
        "status": r.status,
        "final_report": r.final_report,
        "admin_note": r.admin_note,
        "published_at": r.published_at,
        "updated_at": r.updated_at,
    }


@app.get("/api/admin/customer-vaults/{uid}")
def admin_vault_read(uid: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.query(CustomerVault).filter(CustomerVault.user_id == uid).first()
    if not row or not row.cipher_blob:
        return {"profile": {}}
    try:
        return {"profile": decrypt_profile_json(row.cipher_blob), "updated_at": row.updated_at}
    except Exception:
        raise HTTPException(status_code=500, detail="解密失败")


@app.post("/api/admin/timeline-reminders")
def admin_reminder_create(payload: AdminReminderCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    u = db.query(User).filter(User.id == payload.user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")
    row = MemberTimelineReminder(
        tenant_id=u.tenant_id,
        user_id=u.id,
        title=payload.title[:200],
        body=payload.body or "",
        remind_at=payload.remind_at,
        category=payload.category[:40],
        status="pending",
        created_by_role="admin",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "user_id": row.user_id,
        "title": row.title,
        "remind_at": row.remind_at,
        "status": row.status,
        "category": row.category,
    }


@app.patch("/api/admin/timeline-reminders/{rid}")
def admin_reminder_patch(rid: int, patch: AdminReminderPatch, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.query(MemberTimelineReminder).filter(MemberTimelineReminder.id == rid).first()
    if not row:
        raise HTTPException(status_code=404, detail="不存在")
    if patch.title is not None:
        row.title = patch.title[:200]
    if patch.body is not None:
        row.body = patch.body
    if patch.remind_at is not None:
        row.remind_at = patch.remind_at
    if patch.status is not None:
        row.status = patch.status
    if patch.admin_note is not None:
        row.admin_note = patch.admin_note
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "title": row.title,
        "body": row.body,
        "remind_at": row.remind_at,
        "status": row.status,
        "admin_note": row.admin_note,
    }


@app.get("/api/admin/timeline-reminders")
def admin_reminder_list(user_id: int | None = None, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    q = db.query(MemberTimelineReminder).order_by(MemberTimelineReminder.remind_at.desc())
    if user_id:
        q = q.filter(MemberTimelineReminder.user_id == user_id)
    rows = q.limit(500).all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "tenant_id": r.tenant_id,
            "title": r.title,
            "body": r.body,
            "remind_at": r.remind_at,
            "category": r.category,
            "status": r.status,
            "admin_note": r.admin_note,
            "created_by_role": r.created_by_role,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@app.get("/api/admin/users")
def admin_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(User).order_by(User.created_at.desc()).all()


@app.get("/api/admin/plans")
def admin_plans(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(MembershipPlan).order_by(MembershipPlan.price).all()


@app.patch("/api/admin/plans/{plan_code}")
def admin_update_plan(plan_code: str, payload: dict, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    plan = db.query(MembershipPlan).filter(MembershipPlan.code == plan_code).first()
    if not plan:
        raise HTTPException(status_code=404, detail="套餐不存在")
    for key in ["name", "price", "duration_days", "description", "is_active"]:
        if key in payload:
            setattr(plan, key, payload[key])
    db.commit()
    return plan


@app.get("/api/admin/stats")
def admin_stats(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    total = db.query(EligibilityRecord).count()
    intl = db.query(EligibilityRecord).filter(EligibilityRecord.eligibility_type == "international").count()
    return {"users": db.query(User).count(), "tenants": db.query(Tenant).count(), "records_total": total, "international_records": intl, "international_ratio": round(intl / total, 2) if total else 0}


@app.post("/api/admin/recharge-codes")
def admin_create_codes(data: CreateCodeIn, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    codes = []
    for _i in range(max(1, min(data.count, 100))):
        code = f"PRO-{data.plan_code.upper()}-{secrets.token_hex(4).upper()}"
        db.add(RechargeCode(code=code, plan_code=data.plan_code, duration_days=data.duration_days))
        codes.append(code)
    db.commit()
    return {"codes": codes}


@app.get("/api/admin/recharge-codes")
def admin_codes(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(RechargeCode).order_by(RechargeCode.created_at.desc()).limit(200).all()


# --- R4.3 Privacy Endpoints ---

@app.delete("/api/user/{user_id}")
def delete_user_data(
    user_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Delete all personal data for a user (GDPR-style right to erasure).
    Requires admin authentication.
    """
    from .services.data_deletion import DataDeletionService

    deleter = DataDeletionService(db)
    result = deleter.hard_delete_user_data(user_id)

    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Deletion failed"))

    # Audit log
    audit_logger.log(
        actor="admin",
        action=AuditAction.DELETE_USER_DATA,
        resource_type="user",
        resource_id=user_id,
        details={"deleted_records": result.get("records_deleted", 0)},
    )

    return {"ok": True, "message": f"User {user_id} data deleted", "details": result}


@app.get("/api/audit-logs")
def get_audit_logs(
    limit: int = Query(100, ge=1, le=500),
    _: User = Depends(require_admin),
):
    """
    Query audit logs. Requires admin authentication.
    """
    logs = audit_logger.query_logs(limit=limit)
    return {"logs": logs}


# --- R4.3 FIX 4: Self-service data deletion ---

@app.delete("/api/me/data")
def self_delete_data(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete all personal data for the authenticated user.
    Uses current user identity — client cannot specify which user to delete.
    """
    from .services.encryption_at_rest import encrypt_text
    from .services.audit_log import AuditLog

    user_id = user.id
    tenant_id = user.tenant_id

    # Delete eligibility records
    records_deleted = db.query(EligibilityRecord).filter(
        EligibilityRecord.user_id == user_id
    ).delete(synchronize_session=False)

    # Anonymize user record (keep account structure, remove PII)
    user.email = f"deleted_{user_id}@anonymous.local"
    user.name = "[DELETED]"
    user.password_hash = encrypt_text(f"deleted_{user_id}")
    user.role = "member"
    user.permissions = []
    user.is_active = False

    # Revoke all tokens
    db.query(AuthToken).filter(AuthToken.user_id == user_id).delete(synchronize_session=False)

    # Delete vault cipher_blob
    vault = db.query(CustomerVault).filter(
        CustomerVault.tenant_id == tenant_id,
        CustomerVault.user_id == user_id
    ).first()
    if vault:
        vault.cipher_blob = ""

    db.commit()

    # Audit log
    audit_logger = AuditLog(db)
    audit_logger.log_action(
        action_type="self_data_deletion",
        user_id=user_id,
        resource_type="user",
        resource_id=user_id,
        details={"records_deleted": records_deleted},
    )

    return {"ok": True, "message": "Your personal data has been deleted", "records_deleted": records_deleted}


# --- R4.3 FIX 5: Sensitive Data RBAC ---

def require_sensitive_data_access(user: User = Depends(get_current_user)):
    """
    Require the user to have 'sensitive_data_access' permission.
    - Normal user → 403
    - Admin without sensitive_data_access → 403
    - Admin with sensitive_data_access → ALLOW
    """
    permissions = user.permissions or []
    if "sensitive_data_access" in permissions:
        return user
    raise HTTPException(403, "Forbidden: requires sensitive_data_access permission")


# --- R4.3 FIX 6: API Minimization — masked records endpoints ---

def _mask_record(r: EligibilityRecord) -> dict:
    """Return a record dict with sensitive fields masked."""
    return {
        "id": r.id,
        "type": r.eligibility_type,
        "qualified": r.qualified,
        "conclusion": r.conclusion,
        "created_at": r.created_at,
        # Sensitive fields are NOT included in default response
        "raw_input": "[MASKED]",
        "passport_info": "[MASKED]",
    }


def _unmask_record(r: EligibilityRecord) -> dict:
    """Return a record dict with decrypted sensitive fields (requires sensitive_data_access)."""
    from .services.encryption_at_rest import decrypt_json, decrypt_text
    raw_input_data = {}
    if r.raw_input_encrypted:
        raw_input_data = decrypt_json(r.raw_input_encrypted)
    return {
        "id": r.id,
        "type": r.eligibility_type,
        "qualified": r.qualified,
        "conclusion": r.conclusion,
        "created_at": r.created_at,
        "raw_input": raw_input_data,
    }


@app.get("/api/records/{record_id}")
def get_record_detail(
    record_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get record detail — masked by default."""
    record = db.query(EligibilityRecord).filter(
        EligibilityRecord.id == record_id,
        EligibilityRecord.user_id == user.id,
    ).first()
    if not record:
        raise HTTPException(404, "Record not found")
    return _mask_record(record)


@app.get("/api/records/{record_id}/sensitive")
def get_record_sensitive(
    record_id: int,
    user: User = Depends(require_sensitive_data_access),
    db: Session = Depends(get_db),
):
    """Get record detail with decrypted sensitive data — requires sensitive_data_access."""
    record = db.query(EligibilityRecord).filter(
        EligibilityRecord.id == record_id,
    ).first()
    if not record:
        raise HTTPException(404, "Record not found")

    # Audit log
    from .services.audit_log import AuditLog
    audit_logger = AuditLog(db)
    audit_logger.log_action(
        action_type="sensitive_data_access",
        user_id=user.id,
        resource_type="record",
        resource_id=record_id,
        details={"action": "decrypt_raw_input"},
    )

    return _unmask_record(record)
