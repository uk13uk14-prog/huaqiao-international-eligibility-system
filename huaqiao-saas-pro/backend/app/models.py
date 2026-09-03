from datetime import datetime
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.types import JSON
from sqlalchemy.orm import relationship
from .database import Base


class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    tenant_type = Column(String(30), default="personal")
    created_at = Column(DateTime, default=datetime.utcnow)
    users = relationship("User", back_populates="tenant")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    email = Column(String(160), unique=True, index=True, nullable=False)
    name = Column(String(80), default="")
    password_hash = Column(String(160), nullable=False)
    role = Column(String(30), default="member")
    permissions = Column(JSON, default=list)  # R4.3 FIX: fine-grained permissions e.g. ["sensitive_data_access"]
    plan_code = Column(String(40), default="free", index=True)
    membership_until = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    tenant = relationship("Tenant", back_populates="users")


class AuthToken(Base):
    __tablename__ = "auth_tokens"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    token = Column(String(500), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class MembershipPlan(Base):
    __tablename__ = "membership_plans"
    id = Column(Integer, primary_key=True)
    code = Column(String(40), unique=True, index=True, nullable=False)
    name = Column(String(80), nullable=False)
    price = Column(Integer, default=0)
    duration_days = Column(Integer, default=0)
    description = Column(Text, default="")
    features = Column(Text, default="{}")
    is_active = Column(Boolean, default=True)


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    plan_code = Column(String(40), index=True, nullable=False)
    amount = Column(Integer, default=0)
    status = Column(String(30), default="paid")
    source = Column(String(30), default="redeem_code")
    created_at = Column(DateTime, default=datetime.utcnow)


class PaymentOrder(Base):
    __tablename__ = "payment_orders"
    id = Column(Integer, primary_key=True)
    order_no = Column(String(80), unique=True, index=True, nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    plan_code = Column(String(40), index=True, nullable=False)
    channel = Column(String(30), index=True, nullable=False)
    amount = Column(Integer, default=0)
    status = Column(String(30), default="pending", index=True)
    pay_url = Column(Text, default="")
    qr_content = Column(Text, default="")
    provider_trade_no = Column(String(120), default="")
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class RechargeCode(Base):
    __tablename__ = "recharge_codes"
    id = Column(Integer, primary_key=True)
    code = Column(String(80), unique=True, index=True, nullable=False)
    plan_code = Column(String(40), index=True, nullable=False)
    duration_days = Column(Integer, default=30)
    is_used = Column(Boolean, default=False)
    used_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PermissionConfig(Base):
    __tablename__ = "permission_configs"
    id = Column(Integer, primary_key=True)
    plan_code = Column(String(40), unique=True, index=True, nullable=False)
    config = Column(Text, default="{}")


class EligibilityRecord(Base):
    __tablename__ = "eligibility_records"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    eligibility_type = Column(String(30), index=True, nullable=False)
    qualified = Column(Boolean, nullable=False)
    conclusion = Column(String(200), nullable=False)
    reasons = Column(Text, default="[]")
    basis_articles = Column(Text, default="[]")
    recommendations = Column(Text, default="[]")
    suggestions = Column(Text, default="[]")
    raw_input = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class University(Base):
    __tablename__ = "universities"
    id = Column(Integer, primary_key=True)
    ranking = Column(Integer, default=999, index=True)
    name = Column(String(160), unique=True, index=True, nullable=False)
    province = Column(String(80), default="")
    university_type = Column(String(120), default="")
    tags = Column(String(200), default="")
    fields = Column(String(200), default="")
    admission_targets = Column(String(120), default="international,huaqiao")
    advantage_majors = Column(Text, default="")
    description = Column(Text, default="")
    requirements = Column(Text, default="")
    official_url = Column(String(300), default="")
    admission_url = Column(String(300), default="")
    admission_email = Column(String(160), default="")
    admission_phone = Column(String(120), default="")
    admissions_office = Column(String(160), default="")
    is_core = Column(Boolean, default=True, index=True)


class AdmissionSchedule(Base):
    __tablename__ = "admission_schedules"
    id = Column(Integer, primary_key=True)
    university_id = Column(Integer, ForeignKey("universities.id"), index=True, nullable=False)
    year = Column(Integer, default=2026)
    month = Column(Integer, index=True, default=1)
    registration_time = Column(String(160), default="")
    material_deadline = Column(String(160), default="")
    exam_time = Column(String(160), default="")
    reminder = Column(Text, default="")


class CustomerVault(Base):
    """会员客户专属资料（服务端密文存储，与 App 本地备份配对）。"""
    __tablename__ = "customer_vaults"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True, nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    cipher_blob = Column(Text, default="")
    schema_version = Column(Integer, default=1)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StudentMasterProfile(Base):
    """Student Master Profile v2 — encrypted JSON document per student."""
    __tablename__ = "student_master_profiles"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    display_name = Column(String(160), default="")
    cipher_blob = Column(Text, default="")
    schema_version = Column(Integer, default=2)
    source = Column(String(40), default="created")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StudentTimelineItem(Base):
    """Per-student personalized timeline state. Public AdmissionSchedule is never mutated."""
    __tablename__ = "student_timeline_items"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("student_master_profiles.id"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    source_timeline_id = Column(Integer, ForeignKey("admission_schedules.id"), nullable=True, index=True)
    title = Column(String(240), default="")
    description = Column(Text, default="")
    start_date = Column(Date, nullable=True)
    deadline = Column(Date, nullable=True, index=True)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=True)
    university_name = Column(String(160), default="")
    entry_year = Column(Integer, nullable=True)
    application_route = Column(String(40), default="")
    status = Column(String(30), default="NOT_STARTED", index=True)
    completed_at = Column(DateTime, nullable=True)
    student_note = Column(Text, default="")
    is_manual = Column(Boolean, default=False, index=True)
    needs_confirmation = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ExpertConsultation(Base):
    """一对一专家咨询：付费提交 → 系统自动生成初稿 → 人工审核下发。"""
    __tablename__ = "expert_consultations"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    title = Column(String(200), default="")
    question = Column(Text, default="")
    personalization = Column(Text, default="")
    contact_phone = Column(String(40), default="")
    contact_email = Column(String(160), default="")
    contact_wechat = Column(String(80), default="")
    status = Column(String(30), default="pending_ai", index=True)
    ai_draft = Column(Text, default="")
    ai_model = Column(String(120), default="")
    final_report = Column(Text, default="")
    admin_note = Column(Text, default="")
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ConsultationReportVersion(Base):
    __tablename__ = "consultation_report_versions"
    id = Column(Integer, primary_key=True)
    consultation_id = Column(Integer, ForeignKey("expert_consultations.id"), index=True, nullable=False)
    version_no = Column(Integer, default=1)
    content = Column(Text, default="")
    source = Column(String(30), default="ai")
    editor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class MemberTimelineReminder(Base):
    """会员升学/证件/招生节点提醒（年卡、三年卡；后台可追加）。"""
    __tablename__ = "member_timeline_reminders"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    title = Column(String(200), default="")
    body = Column(Text, default="")
    remind_at = Column(DateTime, index=True, nullable=False)
    category = Column(String(40), default="general")
    status = Column(String(20), default="pending", index=True)
    admin_note = Column(Text, default="")
    created_by_role = Column(String(20), default="system")
    created_at = Column(DateTime, default=datetime.utcnow)
