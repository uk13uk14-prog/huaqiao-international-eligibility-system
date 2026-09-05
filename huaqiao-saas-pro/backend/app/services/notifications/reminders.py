"""Timeline → reminder candidates. Personalized only — never blast all universities."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy.orm import Session

from ...models import Notification, NotificationRule, StudentTimelineItem
from .constants import (
    CATEGORY_OPS,
    CATEGORY_TIMELINE,
    COMPLETED_TIMELINE_STATUSES,
    CSCA_EVENT_TYPES,
    DEFAULT_DEADLINE_LADDER,
    PRIORITY_HIGH,
    PRIORITY_NORMAL,
    ROLE_ADMIN,
    ROLE_STUDENT,
    STATUS_READY,
    STATUS_SCHEDULED,
    STATUS_SENT,
    TITLE_EVENT_HINTS,
)
from .copy import ai_organize_copy
from .create import cancel_notification, create_notification, list_admin_user_ids


def infer_event_type(title: str, description: str = "") -> str:
    text = f"{title or ''} {description or ''}"
    for hints, et in TITLE_EVENT_HINTS:
        if any(h in text for h in hints):
            return et
    return "TIMELINE_TASK"


def ensure_default_rules(db: Session) -> int:
    if db.query(NotificationRule).count():
        return 0
    rows: list[NotificationRule] = []
    ladder = [
        (30, "NORMAL", "距离{label}还有30天", "请提前规划材料与报名节奏。"),
        (14, "NORMAL", "距离{label}还有14天", "请确认申请材料是否齐全。"),
        (7, "HIGH", "申请截止仅剩7天：{label}", "建议今天完成材料最终核对。"),
        (3, "HIGH", "申请进入最后3天：{label}", "请立即确认提交状态。"),
        (1, "CRITICAL", "明天截止：{label}", "请马上确认是否已提交。"),
        (0, "CRITICAL", "今天是截止日：{label}", "请确认提交结果，如有问题立即联系顾问。"),
    ]
    for days, prio, title, body in ladder:
        rows.append(NotificationRule(
            event_type="APPLICATION_DEADLINE", days_before=days, enabled=True,
            recipient_type=ROLE_STUDENT, priority=prio,
            title_template=title, body_template=body, category=CATEGORY_TIMELINE,
        ))
        rows.append(NotificationRule(
            event_type="APPLICATION_DEADLINE", days_before=days, enabled=True,
            recipient_type=ROLE_ADMIN,
            priority=PRIORITY_HIGH if days <= 7 else PRIORITY_NORMAL,
            title_template="学生重要截止临近（{days}天）：{label}",
            body_template="请关注学生进度与风险。", category=CATEGORY_OPS,
        ))
    for et in ("MATERIAL_DEADLINE", "EXAM_DATE", "INTERVIEW_DATE", "TIMELINE_TASK"):
        for days, prio in ((14, "NORMAL"), (7, "HIGH"), (3, "HIGH"), (1, "CRITICAL"), (0, "CRITICAL")):
            rows.append(NotificationRule(
                event_type=et, days_before=days, enabled=True,
                recipient_type=ROLE_STUDENT, priority=prio,
                title_template="{label}还有{days}天",
                body_template="请查看时间线并完成对应任务。",
                category=CATEGORY_TIMELINE,
            ))
    db.add_all(rows)
    db.commit()
    return len(rows)



def ensure_csca_rules(db: Session) -> int:
    """Additive CSCA reminder rules (T-30/14/7/3/1/0). Safe when other rules already exist."""
    existing = {
        (row.event_type, row.days_before, row.recipient_type)
        for row in db.query(NotificationRule).filter(NotificationRule.event_type.in_(CSCA_EVENT_TYPES)).all()
    }
    ladder = [
        (30, "NORMAL", "距离{label}还有30天", "请提前准备 CSCA 相关材料与复习计划。"),
        (14, "NORMAL", "距离{label}还有14天", "请确认报名/考试安排是否就绪。"),
        (7, "HIGH", "CSCA 节点仅剩7天：{label}", "建议完成本周备考与材料核对。"),
        (3, "HIGH", "CSCA 进入最后3天：{label}", "请立即确认状态与行程。"),
        (1, "CRITICAL", "明天是 CSCA 节点：{label}", "请马上确认是否已完成对应事项。"),
        (0, "CRITICAL", "今天是 CSCA 节点：{label}", "请确认结果，如有问题联系顾问。"),
    ]
    rows: list[NotificationRule] = []
    for et in CSCA_EVENT_TYPES:
        for days, prio, title, body in ladder:
            key = (et, days, ROLE_STUDENT)
            if key in existing:
                continue
            rows.append(NotificationRule(
                event_type=et, days_before=days, enabled=True,
                recipient_type=ROLE_STUDENT, priority=prio,
                title_template=title, body_template=body, category=CATEGORY_TIMELINE,
            ))
            existing.add(key)
    if rows:
        db.add_all(rows)
        db.commit()
    return len(rows)


def rules_for(db: Session, event_type: str, recipient_type: str) -> list[NotificationRule]:
    return (
        db.query(NotificationRule)
        .filter(
            NotificationRule.event_type == event_type,
            NotificationRule.recipient_type == recipient_type,
            NotificationRule.enabled == True,  # noqa: E712
        )
        .all()
    )


def cancel_reminders_for_completed_item(
    db: Session, item: StudentTimelineItem, *, commit: bool = True
) -> int:
    rows = (
        db.query(Notification)
        .filter(
            Notification.source_type == "student_timeline_item",
            Notification.source_id == str(item.id),
            Notification.status.in_((STATUS_SCHEDULED, STATUS_READY, STATUS_SENT)),
        )
        .all()
    )
    n = 0
    for row in rows:
        if row.read_at:
            continue
        cancel_notification(db, row, commit=False)
        n += 1
    if commit:
        db.commit()
    return n


def generate_for_timeline_item(
    db: Session,
    item: StudentTimelineItem,
    *,
    today: date | None = None,
    also_admin: bool = True,
    commit: bool = True,
) -> list[Notification]:
    _ = today
    ensure_csca_rules(db)
    if not item.deadline:
        return []
    if item.status in COMPLETED_TIMELINE_STATUSES:
        cancel_reminders_for_completed_item(db, item, commit=commit)
        return []

    event_type = infer_event_type(item.title or "", item.description or "")
    label = item.title or (item.university_name or "时间线任务")
    created: list[Notification] = []

    student_rules = rules_for(db, event_type, ROLE_STUDENT)
    if not student_rules:
        student_rules = [
            NotificationRule(
                event_type=event_type, days_before=d, enabled=True,
                recipient_type=ROLE_STUDENT,
                priority="CRITICAL" if d <= 1 else ("HIGH" if d <= 7 else "NORMAL"),
                title_template="{label}还有{days}天",
                body_template="请查看时间线并完成对应任务。",
                category=CATEGORY_TIMELINE,
            )
            for d in DEFAULT_DEADLINE_LADDER
            if event_type == "APPLICATION_DEADLINE" or event_type in CSCA_EVENT_TYPES or d <= 14
        ]

    for rule in student_rules:
        days = int(rule.days_before if rule.days_before is not None else 0)
        fire_date = item.deadline - timedelta(days=days)
        scheduled_at = datetime.combine(fire_date, time(9, 0))
        title, body = ai_organize_copy(
            label=label, days_before=days, deadline=item.deadline,
            title_template=rule.title_template or "",
            body_template=rule.body_template or "",
        )
        row = create_notification(
            db,
            recipient_user_id=item.user_id,
            recipient_role=ROLE_STUDENT,
            title=title, body=body, event_type=event_type,
            category=rule.category or CATEGORY_TIMELINE,
            student_id=item.student_id,
            source_type="student_timeline_item", source_id=str(item.id),
            scheduled_at=scheduled_at,
            priority=rule.priority or PRIORITY_NORMAL,
            action_url=f"/timeline?student_id={item.student_id}&item_id={item.id}",
            action_label="查看时间线",
            commit=False,
        )
        if row is not None:
            created.append(row)

    if also_admin and event_type == "APPLICATION_DEADLINE":
        admin_rules = rules_for(db, "APPLICATION_DEADLINE", ROLE_ADMIN)
        admin_ids = list_admin_user_ids(db)
        for rule in admin_rules:
            days = int(rule.days_before if rule.days_before is not None else 0)
            if days > 7:
                continue
            fire_date = item.deadline - timedelta(days=days)
            scheduled_at = datetime.combine(fire_date, time(9, 0))
            title = f"学生重要截止临近（{days}天）：{label}"
            body = f"学生档案 #{item.student_id} · 截止 {item.deadline.isoformat()}"
            for aid in admin_ids:
                row = create_notification(
                    db,
                    recipient_user_id=aid, recipient_role=ROLE_ADMIN,
                    title=title, body=body,
                    event_type="STUDENT_DEADLINE_APPROACHING",
                    category=CATEGORY_OPS, student_id=item.student_id,
                    source_type="student_timeline_item", source_id=str(item.id),
                    scheduled_at=scheduled_at,
                    priority=rule.priority or PRIORITY_HIGH,
                    action_url=f"/m/students/{item.student_id}",
                    action_label="打开学生360",
                    commit=False,
                )
                if row is not None:
                    created.append(row)

    if commit:
        db.commit()
        for r in created:
            try:
                db.refresh(r)
            except Exception:
                pass
    return created


def scan_student_timelines(
    db: Session,
    *,
    today: date | None = None,
    limit_items: int | None = 500,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Scan personalized student timelines into reminder notifications.

    dry_run=True: count candidates / would-create / dedupe skips only.
    Never sends push, never shows popup, never writes rows when dry_run.
    """
    if not dry_run:
        ensure_default_rules(db)
    today = today or date.today()
    start = today - timedelta(days=1)
    end = today + timedelta(days=31)

    done = (
        db.query(StudentTimelineItem)
        .filter(
            StudentTimelineItem.deadline.isnot(None),
            StudentTimelineItem.deadline >= start,
            StudentTimelineItem.deadline <= end,
            StudentTimelineItem.status.in_(tuple(COMPLETED_TIMELINE_STATUSES)),
        )
        .all()
    )
    cancelled_n = 0
    if not dry_run:
        for item in done:
            cancelled_n += cancel_reminders_for_completed_item(db, item, commit=False)
    else:
        cancelled_n = len(done)

    q = (
        db.query(StudentTimelineItem)
        .filter(
            StudentTimelineItem.deadline.isnot(None),
            StudentTimelineItem.deadline >= start,
            StudentTimelineItem.deadline <= end,
            StudentTimelineItem.status.notin_(tuple(COMPLETED_TIMELINE_STATUSES)),
        )
        .order_by(StudentTimelineItem.deadline.asc())
    )
    if limit_items:
        q = q.limit(limit_items)
    items = q.all()

    if dry_run:
        from .create import build_dedupe_key, find_existing

        would_create = 0
        dedupe_skipped = 0
        for item in items:
            if not item.deadline:
                continue
            event_type = infer_event_type(item.title or "", item.description or "")
            student_rules = rules_for(db, event_type, ROLE_STUDENT)
            days_list = [
                int(r.days_before if r.days_before is not None else 0) for r in student_rules
            ] or list(DEFAULT_DEADLINE_LADDER)
            for days in days_list:
                if event_type != "APPLICATION_DEADLINE" and days > 14 and not student_rules:
                    continue
                fire_date = item.deadline - timedelta(days=days)
                scheduled_at = datetime.combine(fire_date, time(9, 0))
                key = build_dedupe_key(
                    recipient_user_id=item.user_id,
                    student_id=item.student_id,
                    source_type="student_timeline_item",
                    source_id=str(item.id),
                    event_type=event_type,
                    scheduled_at=scheduled_at,
                )
                if find_existing(db, key):
                    dedupe_skipped += 1
                else:
                    would_create += 1
        db.rollback()
        return {
            "dry_run": True,
            "scanned_items": len(items),
            "candidate_count": len(items),
            "would_create_count": would_create,
            "dedupe_skipped_count": dedupe_skipped,
            "would_cancel_completed": cancelled_n,
            "created_or_existing": 0,
            "cancelled": 0,
            "today": today.isoformat(),
        }

    created_n = 0
    for item in items:
        rows = generate_for_timeline_item(db, item, today=today, commit=False)
        created_n += len(rows)
    db.commit()
    return {
        "dry_run": False,
        "scanned_items": len(items),
        "candidate_count": len(items),
        "would_create_count": 0,
        "dedupe_skipped_count": 0,
        "created_or_existing": created_n,
        "cancelled": cancelled_n,
        "today": today.isoformat(),
    }
