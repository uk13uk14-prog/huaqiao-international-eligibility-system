from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, model_validator


class EligibilityInput(BaseModel):
    name: str = Field(..., min_length=1)
    birth_date: str = ""
    current_nationality: str = ""
    has_chinese_nationality: bool = False
    has_foreign_nationality: bool = False
    foreign_nationality_acquired_date: str = ""
    settled_abroad: bool = False
    permanent_residence_country: str = ""
    overseas_residence_months_last_2y: int = 0
    overseas_residence_months_last_4y: int = 0
    annual_months_overseas: int = 0
    has_mainland_household: bool = False
    parent_chinese_citizen: bool = False
    parent_settled_abroad_at_birth: bool = False
    born_abroad: bool = False
    passport_info: str = ""
    household_info: str = ""
    complex_situation: str = ""
    intended_field: str = ""
    score: int | None = None


class EligibilityResult(BaseModel):
    record_id: int
    user_id: int
    eligibility_type: str
    qualified: bool
    conclusion: str
    reasons: list[str]
    basis_articles: list[dict[str, Any]]
    suggestions: list[str]
    recommendations: list[dict[str, Any]] = []
    created_at: datetime


class LawArticle(BaseModel):
    number: int
    title: str
    text: str
    explanation: str
    keywords: list[str]


class UniversityOut(BaseModel):
    id: int
    name: str
    ranking: int
    province: str
    university_type: str
    target: str
    admission_targets: str
    tags: str
    fields: str
    advantage_majors: str
    description: str
    requirements: str
    official_url: str
    admission_url: str = ""
    admission_email: str = ""
    admission_phone: str = ""
    admissions_office: str = ""

    model_config = {"from_attributes": True}


class ScheduleOut(BaseModel):
    id: int
    university_id: int
    university_name: str
    target: str
    ranking: int = 999
    province: str = ""
    tags: str = ""
    fields: str = ""
    year: int
    month: int
    registration_time: str
    material_deadline: str
    exam_time: str
    reminder: str


class RecommendationOut(BaseModel):
    id: int
    name: str
    ranking: int
    province: str
    tags: str
    fields: str
    advantage_majors: str
    admission_timeline: str
    official_url: str
    admission_url: str = ""
    admission_email: str = ""
    admission_phone: str = ""
    admissions_office: str = ""
    match_reason: str


class TelemetrySessionIn(BaseModel):
    client_id: str = Field(..., min_length=8, max_length=64)
    app_version: str = ""
    platform: str = ""


class ConsultationCreate(BaseModel):
    client_id: str = ""
    name: str = ""
    phone: str = ""
    email: str = ""
    wechat: str = ""
    note: str = ""

    @model_validator(mode="after")
    def require_some_content(self):
        if not any([self.name.strip(), self.phone.strip(), self.email.strip(), self.wechat.strip(), self.note.strip()]):
            raise ValueError("请至少填写一项联系方式或需求说明")
        return self


class ConsultationOut(BaseModel):
    id: int
    client_uuid: str
    name: str
    phone: str
    email: str
    wechat: str
    note: str
    status: str
    admin_note: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConsultationPatch(BaseModel):
    status: str | None = None
    admin_note: str | None = None


class AdminOverview(BaseModel):
    unique_clients: int
    total_client_pings: int
    consultation_requests_total: int
    consultation_pending: int
    eligibility_judgments_total: int
