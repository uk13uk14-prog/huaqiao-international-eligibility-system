"""Notification Center HTTP API — student + admin + scheduler tick."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .database import get_db
from .models import Notification, NotificationDevice, User
from .services import notifications as notif
from .services.admin_rbac import require_admin_console
from .services.security import get_current_user


router = APIRouter(tags=["notifications"])


class PrefsIn(BaseModel):
    timeline_enabled: bool | None = None
    expert_enabled: bool | None = None
    account_enabled: bool | None = None
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    timezone: str | None = None


class DeviceIn(BaseModel):
    device_type: str = "web"
    platform: str = ""
    push_provider: str = "IN_APP"
    push_token_encrypted: str = Field(default="", description="Never logged")


def _get_owned(db: Session, user: User, notification_id: int) -> Notification:
    row = db.query(Notification).filter(Notification.id == notification_id).first()
    if not row or row.recipient_user_id != user.id:
        raise HTTPException(status_code=404, detail="通知不存在")
    return row


@router.get("/api/notifications")
def student_list(
    status: str | None = None,
    category: str | None = None,
    unread_only: bool = False,
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = notif.list_for_user(
        db,
        user_id=user.id,
        recipient_role=notif.ROLE_STUDENT,
        status=status,
        category=category,
        unread_only=unread_only,
        limit=limit,
    )
    return {
        "items": [notif.serialize_notification(r) for r in rows],
        "unread_count": notif.unread_count(db, user.id, recipient_role=notif.ROLE_STUDENT),
    }


@router.get("/api/notifications/unread-count")
def student_unread(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"unread_count": notif.unread_count(db, user.id, recipient_role=notif.ROLE_STUDENT)}


@router.get("/api/notifications/popups")
def student_popups(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = notif.pending_popups(db, user.id, recipient_role=notif.ROLE_STUDENT)
    return {"items": [notif.serialize_notification(r) for r in rows]}


@router.post("/api/notifications/{notification_id}/read")
def student_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _get_owned(db, user, notification_id)
    return {"item": notif.serialize_notification(notif.mark_read(db, row))}


@router.post("/api/notifications/{notification_id}/popup-shown")
def student_popup_shown(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = _get_owned(db, user, notification_id)
    return {"item": notif.serialize_notification(notif.mark_popup_shown(db, row))}


@router.get("/api/notifications/preferences")
def student_get_prefs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prefs = notif.get_or_create_prefs(db, user.id)
    return {
        "timeline_enabled": prefs.timeline_enabled,
        "expert_enabled": prefs.expert_enabled,
        "account_enabled": prefs.account_enabled,
        "quiet_hours_start": prefs.quiet_hours_start,
        "quiet_hours_end": prefs.quiet_hours_end,
        "timezone": prefs.timezone,
    }


@router.put("/api/notifications/preferences")
def student_put_prefs(
    body: PrefsIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prefs = notif.get_or_create_prefs(db, user.id)
    for field in (
        "timeline_enabled",
        "expert_enabled",
        "account_enabled",
        "quiet_hours_start",
        "quiet_hours_end",
        "timezone",
    ):
        val = getattr(body, field)
        if val is not None:
            setattr(prefs, field, val)
    db.add(prefs)
    db.commit()
    db.refresh(prefs)
    return {"ok": True}


@router.post("/api/notifications/devices")
def student_register_device(
    body: DeviceIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = NotificationDevice(
        user_id=user.id,
        device_type=body.device_type,
        platform=body.platform,
        push_provider=body.push_provider or "IN_APP",
        push_token_encrypted=body.push_token_encrypted or "",
        enabled=True,
    )
    db.add(row)
    db.commit()
    return {"id": row.id, "push_provider": row.push_provider, "enabled": row.enabled}


@router.get("/api/admin/v1/notifications")
def admin_list(
    status: str | None = None,
    priority: str | None = None,
    pending_only: bool = False,
    unread_only: bool = False,
    limit: int = Query(50, ge=1, le=200),
    admin: User = Depends(require_admin_console),
    db: Session = Depends(get_db),
):
    rows = notif.list_for_user(
        db,
        user_id=admin.id,
        recipient_role=notif.ROLE_ADMIN,
        status=status,
        priority=priority,
        unread_only=unread_only,
        pending_only=pending_only,
        limit=limit,
    )
    return {
        "items": [notif.serialize_notification(r) for r in rows],
        "unread_count": notif.unread_count(db, admin.id, recipient_role=notif.ROLE_ADMIN),
        "providers": notif.provider_status(),
    }


@router.get("/api/admin/v1/notifications/popups")
def admin_popups(admin: User = Depends(require_admin_console), db: Session = Depends(get_db)):
    rows = notif.pending_popups(db, admin.id, recipient_role=notif.ROLE_ADMIN)
    return {"items": [notif.serialize_notification(r) for r in rows]}


@router.post("/api/admin/v1/notifications/{notification_id}/read")
def admin_read(
    notification_id: int,
    admin: User = Depends(require_admin_console),
    db: Session = Depends(get_db),
):
    row = _get_owned(db, admin, notification_id)
    return {"item": notif.serialize_notification(notif.mark_read(db, row))}


@router.post("/api/admin/v1/notifications/{notification_id}/popup-shown")
def admin_popup_shown(
    notification_id: int,
    admin: User = Depends(require_admin_console),
    db: Session = Depends(get_db),
):
    row = _get_owned(db, admin, notification_id)
    return {"item": notif.serialize_notification(notif.mark_popup_shown(db, row))}


@router.post("/api/admin/v1/notifications/scheduler/tick")
def admin_scheduler_tick(
    admin: User = Depends(require_admin_console),
    db: Session = Depends(get_db),
):
    return notif.run_scheduler_tick(db)
