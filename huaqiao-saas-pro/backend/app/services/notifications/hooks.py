"""Domain hooks: AI draft review → admin; publish → student."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ...models import ExpertConsultation, StudentMasterProfile, User
from .constants import CATEGORY_EXPERT, CATEGORY_OPS, PRIORITY_HIGH, PRIORITY_NORMAL, ROLE_ADMIN, ROLE_STUDENT
from .create import create_notification, list_admin_user_ids
from .sanitize import sanitize_text


def notify_admins_ai_review_required(
    db: Session,
    *,
    student: StudentMasterProfile,
    draft: ExpertConsultation | dict,
    actor: User | None = None,
) -> list:
    _ = actor
    draft_id = draft["id"] if isinstance(draft, dict) else draft.id
    name = sanitize_text(student.display_name or f"学生#{student.id}")
    title = f"学生 {name} 有新的 AI 规划待审核"
    body = "请进入 AI Workspace / Student360 审核草稿后再批准发布。"
    action_url = f"/m/ai/{student.id}"
    created = []
    for aid in list_admin_user_ids(db):
        row = create_notification(
            db,
            recipient_user_id=aid, recipient_role=ROLE_ADMIN,
            title=title, body=body, event_type="AI_REVIEW_REQUIRED",
            category=CATEGORY_OPS, student_id=student.id,
            source_type="expert_consultation", source_id=str(draft_id),
            scheduled_at=datetime.utcnow(), status="READY",
            priority=PRIORITY_HIGH, action_url=action_url, action_label="去审核",
            force=True, commit=False,
        )
        if row:
            created.append(row)
    db.commit()
    return created


def notify_student_report_published(
    db: Session,
    *,
    student: StudentMasterProfile,
    draft: ExpertConsultation | dict,
) -> object | None:
    draft_id = draft["id"] if isinstance(draft, dict) else draft.id
    return create_notification(
        db,
        recipient_user_id=student.user_id, recipient_role=ROLE_STUDENT,
        title="新的专家规划已发布",
        body="顾问已发布一对一规划报告，点击查看。",
        event_type="EXPERT_REPORT_PUBLISHED", category=CATEGORY_EXPERT,
        student_id=student.id, source_type="expert_consultation",
        source_id=str(draft_id), scheduled_at=datetime.utcnow(), status="READY",
        priority=PRIORITY_NORMAL, action_url=f"/consultations/{draft_id}",
        action_label="查看规划", force=True, commit=True,
    )
