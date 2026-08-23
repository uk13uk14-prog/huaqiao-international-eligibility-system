from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from .database import Base


class UserInfo(Base):
    __tablename__ = "user_info"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(80), nullable=False)
    birth_date = Column(String(20), default="")
    current_nationality = Column(String(80), default="")
    has_chinese_nationality = Column(Boolean, default=False)
    has_foreign_nationality = Column(Boolean, default=False)
    passport_info = Column(Text, default="")
    household_info = Column(Text, default="")
    residence_records = Column(Text, default="{}")
    family_info = Column(Text, default="{}")
    # R4.3 FIX: Encrypted columns for sensitive data at rest
    passport_info_encrypted = Column(Text, nullable=True)
    household_info_encrypted = Column(Text, nullable=True)
    passport_blind_index = Column(String(64), nullable=True)
    id_card_blind_index = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    records = relationship("EligibilityRecord", back_populates="user")


class EligibilityRecord(Base):
    __tablename__ = "eligibility_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_info.id"), nullable=False)
    eligibility_type = Column(String(30), index=True, nullable=False)
    qualified = Column(Boolean, nullable=False)
    conclusion = Column(String(200), nullable=False)
    reasons = Column(Text, nullable=False)
    basis_articles = Column(Text, nullable=False)
    suggestions = Column(Text, default="")
    raw_input = Column(Text, default="{}")
    # R4.3 FIX: Encrypted raw_input for sensitive data at rest
    raw_input_encrypted = Column(Text, nullable=True)
    passport_blind_index = Column(String(64), nullable=True)
    id_card_blind_index = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("UserInfo", back_populates="records")


class University(Base):
    __tablename__ = "universities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), unique=True, index=True, nullable=False)
    ranking = Column(Integer, default=999, index=True)
    province = Column(String(80), default="")
    university_type = Column(String(80), default="")
    target = Column(String(40), index=True, nullable=False)
    admission_targets = Column(String(120), default="huaqiao,international", index=True)
    tags = Column(String(200), default="")
    fields = Column(String(200), default="")
    advantage_majors = Column(Text, default="")
    description = Column(Text, default="")
    requirements = Column(Text, default="")
    official_url = Column(String(300), default="")
    admission_url = Column(String(300), default="")
    admission_email = Column(String(160), default="")
    admission_phone = Column(String(120), default="")
    admissions_office = Column(String(160), default="")


class AdmissionSchedule(Base):
    __tablename__ = "admission_schedules"

    id = Column(Integer, primary_key=True, index=True)
    university_id = Column(Integer, ForeignKey("universities.id"), nullable=False)
    year = Column(Integer, index=True, nullable=False)
    month = Column(Integer, index=True, nullable=False)
    registration_time = Column(String(160), default="")
    material_deadline = Column(String(160), default="")
    exam_time = Column(String(160), default="")
    reminder = Column(Text, default="")

    university = relationship("University")


class AppClient(Base):
    """客户端安装/打开统计：每次打开应用上报一次，按 client_uuid 去重统计使用人数。"""
    __tablename__ = "app_clients"

    id = Column(Integer, primary_key=True, index=True)
    client_uuid = Column(String(64), unique=True, index=True, nullable=False)
    first_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ping_count = Column(Integer, default=1, nullable=False)
    app_version = Column(String(40), default="")
    platform = Column(String(40), default="")
    user_agent = Column(String(500), default="")


class ConsultationRequest(Base):
    """一对一规划咨询：用户在 App 内提交的线索，后台查看与跟进。"""
    __tablename__ = "consultation_requests"

    id = Column(Integer, primary_key=True, index=True)
    client_uuid = Column(String(64), default="", index=True)
    name = Column(String(80), default="")
    phone = Column(String(40), default="")
    email = Column(String(160), default="")
    wechat = Column(String(80), default="")
    note = Column(Text, default="")
    status = Column(String(20), default="pending", index=True)
    admin_note = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
