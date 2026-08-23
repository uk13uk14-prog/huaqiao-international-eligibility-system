from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field, model_validator


class RegisterIn(BaseModel):
    tenant_name: str = Field(..., min_length=2)
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)
    name: str = ""
    tenant_type: str = "personal"


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    token: str
    user: dict[str, Any]


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
    has_denationalization_certificate: bool = False
    denationalization_certificate_info: str = ""
    parent_chinese_citizen: bool = False
    parent_settled_abroad_at_birth: bool = False
    born_abroad: bool = False
    intended_field: str = "综合"
    score: int | None = None
    passport_info: str = ""
    household_info: str = ""
    complex_situation: str = ""


class RedeemIn(BaseModel):
    code: str


class CreatePaymentIn(BaseModel):
    plan_code: str
    channel: str = "mock"


class CreateCodeIn(BaseModel):
    plan_code: str
    duration_days: int = 30
    count: int = 1


class CustomerVaultUpsert(BaseModel):
    profile: dict = Field(default_factory=dict)


class ExpertConsultationCreate(BaseModel):
    title: str = ""
    question: str = Field(..., min_length=4)
    personalization: str = ""
    contact_phone: str = ""
    contact_email: str = ""
    contact_wechat: str = ""

    @model_validator(mode="after")
    def need_contact(self):
        if not any([self.contact_phone.strip(), self.contact_email.strip(), self.contact_wechat.strip()]):
            raise ValueError("请至少填写一种联系方式")
        return self


class AdminExpertConsultationPatch(BaseModel):
    status: str | None = None
    final_report: str | None = None
    admin_note: str | None = None


class AdminReminderCreate(BaseModel):
    user_id: int
    title: str = Field(..., min_length=2)
    body: str = ""
    remind_at: datetime
    category: str = "custom"


class AdminReminderPatch(BaseModel):
    title: str | None = None
    body: str | None = None
    remind_at: datetime | None = None
    status: str | None = None
    admin_note: str | None = None
