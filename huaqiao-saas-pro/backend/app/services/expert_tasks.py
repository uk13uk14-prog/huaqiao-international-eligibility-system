import json

from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import ConsultationReportVersion, CustomerVault, ExpertConsultation
from .expert_report import generate_expert_consult_draft
from .vault_crypto import decrypt_profile_json


async def run_expert_ai_draft(consultation_id: int):
    db: Session = SessionLocal()
    try:
        row = db.query(ExpertConsultation).filter(ExpertConsultation.id == consultation_id).first()
        if not row or row.status not in ("pending_ai",):
            return
        profile_hint = ""
        vault = db.query(CustomerVault).filter(CustomerVault.user_id == row.user_id).first()
        if vault and vault.cipher_blob:
            try:
                profile_hint = json.dumps(decrypt_profile_json(vault.cipher_blob), ensure_ascii=False)[:8000]
            except Exception:
                profile_hint = ""
        result = await generate_expert_consult_draft(row.question or "", row.personalization or "", profile_hint)
        row.ai_draft = result["text"]
        row.ai_model = result.get("model", "")
        row.status = "draft_ready"
        last_v = db.query(ConsultationReportVersion).filter(ConsultationReportVersion.consultation_id == row.id).order_by(ConsultationReportVersion.version_no.desc()).first()
        vn = (last_v.version_no + 1) if last_v else 1
        db.add(
            ConsultationReportVersion(
                consultation_id=row.id,
                version_no=vn,
                content=result["text"],
                source="ai",
                editor_user_id=None,
            )
        )
        db.commit()
    except Exception:
        row = db.query(ExpertConsultation).filter(ExpertConsultation.id == consultation_id).first()
        if row:
            row.status = "ai_failed"
            row.ai_draft = row.ai_draft or "生成初稿失败，请由顾问人工撰写或稍后重试。"
            db.commit()
    finally:
        db.close()
