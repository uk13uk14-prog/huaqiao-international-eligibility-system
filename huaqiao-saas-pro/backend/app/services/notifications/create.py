"""Create / list / read notifications with dedupe + preference gates."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from ...models import Notification, NotificationPreference, User
from .constants import (
    CATEGORY_ACCOUNT,
    CATEGORY_EXPERT,
    CATEGORY_TIMELINE,
    NON_DISMISSABLE_EVENTS,
    PRIORITY_CRITICAL,
    PRIORITY_HIGH,
    PRIORITY_NORMAL,
    STATUS_CANCELLED,
    STATUS_READY,
    STATUS_READ,
    STATUS_SCHEDULED,
    STATUS_SENT,
)
from .sanitize import sanitize_text


def build_dedupe_key(
    *,
    recipient_user_id: int,
    student_id: int | None,
    source_type: str,
    source_id: str,
    event_type: str,
    scheduled_at: datetime | None,
) -> str:
    sched = scheduled_at.strftime("%Y%m%d%H%M") if scheduled_at else "nosched"
    sid = student_id if student_id is not None else 0
    return f"{recipient_user_id}:{sid}:{source_type}:{source_id}:{event_type}:{sched}"


def get_or_create_prefs(db: Session, user_id: int) -> NotificationPreference:
    row = db.query(NotificationPreference).filter(NotificationPreference.user_id == user_id).first()
    if row:
        return row
    row = NotificationPreference(user_id=user_id)
    db.add(row)
    db.flush()
    return row


def preference_allows(
    prefs: NotificationPreference,
    *,
    category: str,
    event_type: str,
    priority: str,
) -> bool:
    prio = (priority or PRIORITY_NORMAL).upper()
    et = (event_type or "").upper()
    if et in NON_DISMISSABLE_EVENTS and prio in (PRIORITY_HIGH, PRIORITY_CRITICAL):
        return True
    cat = (category or CATEGORY_TIMELINE).lower()
    if cat == CATEGORY_TIMELINE and not prefs.timeline_enabled:
        return False
    if cat == CATEGORY_EXPERT and not prefs.expert_enabled:
        return False
    if cat == CATEGORY_ACCOUNT and not prefs.account_enabled:
        return False
    return True


def find_existing(db: Session, dedupe_key: str) -> Notification | None:
    if not dedupe_key:
        return None
    return (
        db.query(Notification)
        .filter(
            Notification.dedupe_key == dedupe_key,
            Notification.status.in_((STATUS_SCHEDULED, STATUS_READY, STATUS_SENT, STATUS_READ)),
        )
        .order_by(Notification.id.desc())
        .first()
    )


def create_notification(
    db: Session,
    *,
    recipient_user_id: int,
    recipient_role: str,
    title: str,
    body: str = "",
    event_type: str,
    category: str = CATEGORY_TIMELINE,
    student_id: int | None = None,
    source_type: str = "",
    source_id: str = "",
    scheduled_at: datetime | None = None,
    status: str | None = None,
    priority: str = PRIORITY_NORMAL,
    action_url: str = "",
    action_label: str = "",
    force: bool = False,
    commit: bool = True,
) -> Notification | None:
    prefs = get_or_create_prefs(db, recipient_user_id)
    if not force and not preference_allows(
        prefs, category=category, event_type=event_type, priority=priority
    ):
        return None

    clean_title = sanitize_text(title) or "你有一条新提醒"
    clean_body = sanitize_text(body)
    now = datetime.utcnow()
    sched = scheduled_at
    if status is None:
        if sched and sched > now:
            status = STATUS_SCHEDULED
        else:
            status = STATUS_READY
            sched = sched or now

    dedupe_key = build_dedupe_key(
        recipient_user_id=recipient_user_id,
        student_id=student_id,
        source_type=source_type or "",
        source_id=str(source_id or ""),
        event_type=event_type,
        scheduled_at=sched,
    )
    existing = find_existing(db, dedupe_key)
    if existing:
        return existing

    row = Notification(
        recipient_user_id=recipient_user_id,
        recipient_role=recipient_role,
        student_id=student_id,
        category=category,
        event_type=event_type,
        title=clean_title,
        body=clean_body,
        source_type=source_type or "",
        source_id=str(source_id or ""),
        scheduled_at=sched,
        status=status,
        priority=(priority or PRIORITY_NORMAL).upper(),
        action_url=action_url or "",
        action_label=action_label or "",
        dedupe_key=dedupe_key,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()
    return row


def serialize_notification(row: Notification) -> dict[str, Any]:
    return {
        "id": row.id,
        "recipient_user_id": row.recipient_user_id,
        "recipient_role": row.recipient_role,
        "student_id": row.student_id,
        "category": row.category,
        "event_type": row.event_type,
        "title": row.title,
        "body": row.body,
        "source_type": row.source_type,
        "source_id": row.source_id,
        "scheduled_at": row.scheduled_at.isoformat() if row.scheduled_at else None,
        "sent_at": row.sent_at.isoformat() if row.sent_at else None,
        "read_at": row.read_at.isoformat() if row.read_at else None,
        "status": row.status,
        "priority": row.priority,
        "action_url": row.action_url or "",
        "action_label": row.action_label or "",
        "popup_shown_at": row.popup_shown_at.isoformat() if row.popup_shown_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "unread": row.read_at is None and row.status != STATUS_CANCELLED,
    }


def mark_read(db: Session, row: Notification) -> Notification:
    now = datetime.utcnow()
    row.read_at = now
    row.status = STATUS_READ
    row.updated_at = now
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def mark_popup_shown(db: Session, row: Notification) -> Notification:
    now = datetime.utcnow()
    row.popup_shown_at = now
    row.updated_at = now
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def cancel_notification(db: Session, row: Notification, *, commit: bool = True) -> Notification:
    row.status = STATUS_CANCELLED
    row.updated_at = datetime.utcnow()
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()
    return row


def list_for_user(
    db: Session,
    *,
    user_id: int,
    recipient_role: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    unread_only: bool = False,
    pending_only: bool = False,
    limit: int = 50,
) -> list[Notification]:
    q = db.query(Notification).filter(Notification.recipient_user_id == user_id)
    if recipient_role:
        q = q.filter(Notification.recipient_role == recipient_role)
    if status:
        q = q.filter(Notification.status == status)
    if priority:
        q = q.filter(Notification.priority == priority.upper())
    if category:
        q = q.filter(Notification.category == category)
    if unread_only:
        q = q.filter(Notification.read_at.is_(None), Notification.status != STATUS_CANCELLED)
    if pending_only:
        q = q.filter(
            Notification.read_at.is_(None),
            Notification.status.in_((STATUS_READY, STATUS_SENT, STATUS_SCHEDULED)),
        )
    return q.order_by(Notification.created_at.desc()).limit(limit).all()


def unread_count(db: Session, user_id: int, *, recipient_role: str | None = None) -> int:
    q = db.query(Notification).filter(
        Notification.recipient_user_id == user_id,
        Notification.read_at.is_(None),
        Notification.status.in_((STATUS_READY, STATUS_SENT, STATUS_SCHEDULED)),
    )
    if recipient_role:
        q = q.filter(Notification.recipient_role == recipient_role)
    return q.count()


def pending_popups(
    db: Session, user_id: int, *, recipient_role: str | None = None
) -> list[Notification]:
    q = db.query(Notification).filter(
        Notification.recipient_user_id == user_id,
        Notification.status.in_((STATUS_READY, STATUS_SENT)),
        Notification.priority.in_((PRIORITY_HIGH, PRIORITY_CRITICAL)),
        Notification.read_at.is_(None),
    )
    if recipient_role:
        q = q.filter(Notification.recipient_role == recipient_role)
    rows = q.order_by(Notification.created_at.desc()).limit(20).all()
    out: list[Notification] = []
    for row in rows:
        if row.priority == PRIORITY_CRITICAL:
            out.append(row)
        elif row.priority == PRIORITY_HIGH and row.popup_shown_at is None:
            out.append(row)
    return out


def list_admin_user_ids(db: Session) -> list[int]:
    q = db.query(User).filter(User.role == "admin")
    if hasattr(User, "is_active"):
        q = q.filter(User.is_active == True)  # noqa: E712
    return [u.id for u in q.all()]

get_or_create_prefs = get_or_create_prefs
