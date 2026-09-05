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
    student_profile_limit_override = Column(Integer, nullable=True)  # account-level seat override
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
    # Phase 3 / draft 007: nullable until backfill; new writes should set student_id.
    student_id = Column(Integer, ForeignKey("student_master_profiles.id"), index=True, nullable=True)
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
    status = Column(String(20), default="ACTIVE", index=True)  # ACTIVE | ARCHIVED | DELETED
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    archived_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    # CRM V1 (migration 010) — operational fields; never put assignee only in cipher JSON
    assignee_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    assigned_at = Column(DateTime, nullable=True)
    assigned_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    crm_stage = Column(String(40), default="UNASSIGNED", index=True)
    risk_level = Column(String(20), default="NONE")
    next_action = Column(Text, default="")
    next_follow_up_at = Column(DateTime, nullable=True, index=True)
    last_follow_up_at = Column(DateTime, nullable=True)
    identity_track = Column(String(40), default="")


class StudentFollowUp(Base):
    """CRM follow-up / activity log. AI_ASSISTED must never pretend to be HUMAN."""
    __tablename__ = "student_follow_ups"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("student_master_profiles.id"), index=True, nullable=False)
    operator_user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    operator_type = Column(String(20), default="STAFF")  # ADMIN | STAFF | SYSTEM
    source = Column(String(20), default="HUMAN")  # HUMAN | AI_ASSISTED | SYSTEM
    type = Column(String(40), default="NOTE")
    content = Column(Text, default="")
    summary = Column(String(240), default="")
    next_action = Column(Text, nullable=True)
    next_follow_up_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


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
    """一对一专家咨询 / Admin AI Expert：DRAFT → REVIEWED → APPROVED → PUBLISHED。"""
    __tablename__ = "expert_consultations"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    # Admin AI Expert V1 — required for safe multi-student isolation on new writes.
    student_id = Column(Integer, ForeignKey("student_master_profiles.id"), index=True, nullable=True)
    assigned_consultant_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    title = Column(String(200), default="")
    question = Column(Text, default="")
    personalization = Column(Text, default="")
    contact_phone = Column(String(40), default="")
    contact_email = Column(String(160), default="")
    contact_wechat = Column(String(80), default="")
    # Legacy: pending_ai/draft_ready/published; Admin V1: DRAFT/REVIEWED/APPROVED/PUBLISHED/ARCHIVED
    status = Column(String(30), default="pending_ai", index=True)
    report_kind = Column(String(60), default="", index=True)
    ai_provider = Column(String(40), default="")
    ai_draft = Column(Text, default="")
    ai_model = Column(String(120), default="")
    # Structured AI payload JSON (summary/risk_items/...) — never contains full ID/passport.
    payload_json = Column(Text, default="{}")
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
    # ai | ai_draft | edited | approved | published | admin_edit (legacy)
    source = Column(String(30), default="ai")
    editor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class AuditEvent(Base):
    """Durable admin/privacy audit (replaces in-memory-only AuditLogger for Admin V1)."""
    __tablename__ = "audit_events"
    id = Column(Integer, primary_key=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    action = Column(String(80), nullable=False, index=True)
    resource_type = Column(String(80), nullable=False, default="")
    resource_id = Column(String(120), nullable=True)
    student_id = Column(Integer, ForeignKey("student_master_profiles.id"), index=True, nullable=True)
    metadata_json = Column(Text, default="{}")
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



# ---------------------------------------------------------------------------
# Notification Center V1
# ---------------------------------------------------------------------------

class Notification(Base):
    """Unified in-app notification (student + admin). Push is provider-abstracted."""
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    recipient_user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    recipient_role = Column(String(30), nullable=False, index=True)  # STUDENT_SIDE | ADMIN_SIDE
    student_id = Column(Integer, ForeignKey("student_master_profiles.id"), index=True, nullable=True)
    category = Column(String(40), default="timeline", index=True)
    event_type = Column(String(60), nullable=False, index=True)
    title = Column(String(240), nullable=False, default="")
    body = Column(Text, default="")
    source_type = Column(String(40), default="")
    source_id = Column(String(120), default="")
    scheduled_at = Column(DateTime, index=True, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="SCHEDULED", index=True)
    priority = Column(String(20), default="NORMAL", index=True)  # LOW|NORMAL|HIGH|CRITICAL
    action_url = Column(String(400), default="")
    action_label = Column(String(80), default="")
    dedupe_key = Column(String(240), default="", index=True)
    popup_shown_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NotificationRule(Base):
    __tablename__ = "notification_rules"
    id = Column(Integer, primary_key=True)
    event_type = Column(String(60), nullable=False, index=True)
    days_before = Column(Integer, nullable=True)
    hours_before = Column(Integer, nullable=True)
    enabled = Column(Boolean, default=True, index=True)
    recipient_type = Column(String(30), nullable=False, default="STUDENT_SIDE", index=True)
    priority = Column(String(20), default="NORMAL")
    title_template = Column(String(240), default="")
    body_template = Column(Text, default="")
    category = Column(String(40), default="timeline")
    created_at = Column(DateTime, default=datetime.utcnow)


class NotificationDevice(Base):
    __tablename__ = "notification_devices"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    device_type = Column(String(40), default="web")
    platform = Column(String(40), default="")
    push_provider = Column(String(20), default="IN_APP")
    push_token_encrypted = Column(Text, default="")
    enabled = Column(Boolean, default=True, index=True)
    last_seen_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, index=True, nullable=False)
    timeline_enabled = Column(Boolean, default=True)
    expert_enabled = Column(Boolean, default=True)
    account_enabled = Column(Boolean, default=True)
    quiet_hours_start = Column(String(8), default="22:00")
    quiet_hours_end = Column(String(8), default="08:00")
    timezone = Column(String(64), default="Asia/Shanghai")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
