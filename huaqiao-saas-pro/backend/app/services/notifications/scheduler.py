"""Safe hourly scheduler: promote SCHEDULED→READY, deliver, bounded retry."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from ...models import Notification, NotificationDevice
from .constants import (
    MAX_SEND_RETRIES,
    PROVIDER_IN_APP,
    STATUS_FAILED,
    STATUS_READY,
    STATUS_SCHEDULED,
    STATUS_SENT,
)
from .create import get_or_create_prefs
from .providers import deliver
from .quiet_hours import next_quiet_end, should_defer_send
from .reminders import scan_student_timelines

_RETRY_COUNTS: dict[int, int] = {}


def promote_due(db: Session, *, now: datetime | None = None) -> int:
    now = now or datetime.utcnow()
    rows = (
        db.query(Notification)
        .filter(Notification.status == STATUS_SCHEDULED, Notification.scheduled_at <= now)
        .limit(500)
        .all()
    )
    for row in rows:
        row.status = STATUS_READY
        row.updated_at = now
        db.add(row)
    db.commit()
    return len(rows)


def send_ready(db: Session, *, now: datetime | None = None, limit: int = 200) -> dict[str, Any]:
    now = now or datetime.utcnow()
    rows = (
        db.query(Notification)
        .filter(Notification.status == STATUS_READY)
        .order_by(Notification.id.asc())
        .limit(limit)
        .all()
    )
    sent = deferred = failed = 0
    for row in rows:
        prefs = get_or_create_prefs(db, row.recipient_user_id)
        if should_defer_send(row.priority or "", prefs):
            row.scheduled_at = next_quiet_end(
                now,
                quiet_start=prefs.quiet_hours_start,
                quiet_end=prefs.quiet_hours_end,
                timezone=prefs.timezone,
            )
            row.status = STATUS_SCHEDULED
            row.updated_at = now
            db.add(row)
            deferred += 1
            continue

        devices = (
            db.query(NotificationDevice)
            .filter(
                NotificationDevice.user_id == row.recipient_user_id,
                NotificationDevice.enabled == True,  # noqa: E712
            )
            .all()
        )
        ok_any = False
        if not devices:
            result = deliver(
                provider_name=PROVIDER_IN_APP,
                device_token="",
                notification_id=row.id,
                title=row.title,
                body=row.body,
                priority=row.priority or "",
                action_url=row.action_url or "",
                for_lockscreen=False,
            )
            ok_any = result.ok
        else:
            for device in devices:
                result = deliver(
                    provider_name=device.push_provider or PROVIDER_IN_APP,
                    device_token="",
                    notification_id=row.id,
                    title=row.title,
                    body=row.body,
                    priority=row.priority or "",
                    action_url=row.action_url or "",
                    for_lockscreen=device.push_provider != PROVIDER_IN_APP,
                )
                ok_any = ok_any or result.ok
                device.last_seen_at = now
                db.add(device)

        if ok_any:
            row.status = STATUS_SENT
            row.sent_at = now
            row.updated_at = now
            _RETRY_COUNTS.pop(row.id, None)
            db.add(row)
            sent += 1
        else:
            attempts = _RETRY_COUNTS.get(row.id, 0) + 1
            _RETRY_COUNTS[row.id] = attempts
            if attempts >= MAX_SEND_RETRIES:
                row.status = STATUS_FAILED
                row.updated_at = now
                failed += 1
            db.add(row)
    db.commit()
    return {"sent": sent, "deferred": deferred, "failed": failed, "examined": len(rows)}


def run_scheduler_tick(db: Session, *, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.utcnow()
    scan = scan_student_timelines(db, today=now.date())
    promoted = promote_due(db, now=now)
    delivery = send_ready(db, now=now)
    return {
        "ok": True,
        "at": now.isoformat(),
        "scan": scan,
        "promoted": promoted,
        "delivery": delivery,
        "max_retries": MAX_SEND_RETRIES,
    }
