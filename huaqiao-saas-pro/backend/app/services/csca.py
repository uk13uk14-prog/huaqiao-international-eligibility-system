"""CSCA Exam Module V1 — profile section, timeline sync, display helpers.

Safety:
- Never invent official dates. Missing dates → 「待官方公布」.
- Timeline / notification nodes only when a real date exists
  (student-entered / admin-entered / official).
- Does not change international / 华侨 eligibility engines.
- Does not hardcode university CSCA requirements.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from ..models import StudentTimelineItem
from .notifications.reminders import generate_for_timeline_item

CSCA_STATUSES = [
    "NOT_PLANNED",
    "PLANNED",
    "REGISTERED",
    "TAKEN",
    "RESULT_AVAILABLE",
]

CSCA_STATUS_LABELS = {
    "NOT_PLANNED": "未计划",
    "PLANNED": "计划参加",
    "REGISTERED": "已报名",
    "TAKEN": "已考试",
    "RESULT_AVAILABLE": "成绩已出",
}

DATE_SOURCES = ("", "student", "admin", "official")

PENDING_OFFICIAL = "待官方公布"

# Distinctive titles — used for upsert + notification event inference.
CSCA_TIMELINE_SPECS = (
    {
        "key": "registration_deadline",
        "title": "CSCA报名截止",
        "marker": "[csca:registration_deadline]",
        "date_field": "csca_registration_deadline",
        "source_field": "registration_deadline_source",
        "description": "CSCA 考试报名截止日期（仅在有真实日期时生成）",
    },
    {
        "key": "exam_date",
        "title": "CSCA考试",
        "marker": "[csca:exam_date]",
        "date_field": "csca_exam_date",
        "source_field": "exam_date_source",
        "description": "CSCA 考试日期（仅在有真实日期时生成）",
    },
    {
        "key": "result_date",
        "title": "CSCA成绩发布",
        "marker": "[csca:result_date]",
        "date_field": "csca_result_date",
        "source_field": "result_date_source",
        "description": "CSCA 成绩发布日期（仅在有真实日期时生成）",
    },
)


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def empty_csca(**overrides) -> dict[str, Any]:
    row = {
        "csca_status": "NOT_PLANNED",
        "csca_exam_date": "",
        "csca_registration_deadline": "",
        "csca_result_date": "",
        "csca_score": "",
        "csca_level": "",
        "csca_notes": "",
        "registration_deadline_source": "",
        "exam_date_source": "",
        "result_date_source": "",
        "updated_at": "",
    }
    row.update(overrides)
    return row


def parse_real_date(value: Any) -> date | None:
    """Return a date only when value is a real ISO date. Never invent."""
    text = str(value or "").strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered in {"tbd", "n/a", "na", "待定", "未知", "待官方公布", PENDING_OFFICIAL.lower()}:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def normalize_csca(raw: dict | None) -> dict[str, Any]:
    base = empty_csca()
    incoming = raw if isinstance(raw, dict) else {}
    out = {**base}
    for key in base:
        if key in incoming:
            out[key] = incoming[key]

    status = str(out.get("csca_status") or "NOT_PLANNED").upper()
    if status not in CSCA_STATUSES:
        status = "NOT_PLANNED"
    out["csca_status"] = status

    for field in ("csca_exam_date", "csca_registration_deadline", "csca_result_date"):
        parsed = parse_real_date(out.get(field))
        out[field] = parsed.isoformat() if parsed else ""

    for src_field in ("registration_deadline_source", "exam_date_source", "result_date_source"):
        src = str(out.get(src_field) or "").strip().lower()
        out[src_field] = src if src in DATE_SOURCES else ""

    # Date without source → treat as student-entered (explicit input).
    if out["csca_registration_deadline"] and not out["registration_deadline_source"]:
        out["registration_deadline_source"] = "student"
    if out["csca_exam_date"] and not out["exam_date_source"]:
        out["exam_date_source"] = "student"
    if out["csca_result_date"] and not out["result_date_source"]:
        out["result_date_source"] = "student"

    out["csca_score"] = str(out.get("csca_score") or "")
    out["csca_level"] = str(out.get("csca_level") or "")
    out["csca_notes"] = str(out.get("csca_notes") or "")
    out["updated_at"] = str(out.get("updated_at") or "")
    return out


def display_date(value: Any, source: str = "") -> str:
    """UI helper: real date or 待官方公布. Never invent."""
    _ = source
    parsed = parse_real_date(value)
    if parsed:
        return parsed.isoformat()
    return PENDING_OFFICIAL


def csca_card(profile_or_csca: dict | None) -> dict[str, Any]:
    """Public display card for student UI / admin 360 / exam center."""
    if isinstance(profile_or_csca, dict) and "csca_status" in profile_or_csca:
        c = normalize_csca(profile_or_csca)
    elif isinstance(profile_or_csca, dict):
        c = normalize_csca(profile_or_csca.get("csca"))
    else:
        c = normalize_csca(None)
    status = c["csca_status"]
    return {
        "csca_status": status,
        "csca_status_label": CSCA_STATUS_LABELS.get(status, status),
        "csca_registration_deadline": display_date(
            c["csca_registration_deadline"], c["registration_deadline_source"]
        ),
        "csca_exam_date": display_date(c["csca_exam_date"], c["exam_date_source"]),
        "csca_result_date": display_date(c["csca_result_date"], c["result_date_source"]),
        "csca_registration_deadline_raw": c["csca_registration_deadline"] or None,
        "csca_exam_date_raw": c["csca_exam_date"] or None,
        "csca_result_date_raw": c["csca_result_date"] or None,
        "registration_deadline_source": c["registration_deadline_source"] or None,
        "exam_date_source": c["exam_date_source"] or None,
        "result_date_source": c["result_date_source"] or None,
        "csca_score": c["csca_score"] or None,
        "csca_level": c["csca_level"] or None,
        "csca_notes": c["csca_notes"] or "",
        "updated_at": c["updated_at"] or None,
        "has_any_real_date": bool(
            c["csca_registration_deadline"] or c["csca_exam_date"] or c["csca_result_date"]
        ),
        "official_date_available": any(
            c.get(f) == "official"
            for f in ("registration_deadline_source", "exam_date_source", "result_date_source")
        ),
        "timeline_eligible": status in ("PLANNED", "REGISTERED"),
        "pending_official_label": PENDING_OFFICIAL,
        # Planning / university context — expose only; do NOT imply requirements.
        "planning_hints": {
            "csca_status": status,
            "csca_score": c["csca_score"] or None,
            "note": "供未来院校/专业规划读取；本阶段不硬编码任何大学必须 CSCA。",
        },
    }


def should_sync_timeline(csca: dict) -> bool:
    c = normalize_csca(csca)
    return c["csca_status"] in ("PLANNED", "REGISTERED")


def _find_csca_item(
    db: Session, student_id: int, user_id: int, marker: str, title: str
) -> StudentTimelineItem | None:
    rows = (
        db.query(StudentTimelineItem)
        .filter(
            StudentTimelineItem.student_id == student_id,
            StudentTimelineItem.user_id == user_id,
            StudentTimelineItem.is_manual == True,  # noqa: E712
        )
        .all()
    )
    for row in rows:
        blob = f"{row.title or ''} {row.description or ''} {row.student_note or ''}"
        if marker in blob:
            return row
    for row in rows:
        if (row.title or "") == title:
            return row
    return None


def sync_csca_timeline(
    db: Session,
    *,
    student_id: int,
    user_id: int,
    tenant_id: int,
    csca: dict,
    commit: bool = True,
) -> dict[str, Any]:
    """Upsert / remove CSCA timeline nodes. Dates must be real — never invent."""
    c = normalize_csca(csca)
    created: list[str] = []
    updated: list[str] = []
    removed: list[str] = []
    notified: list[dict[str, Any]] = []
    active = should_sync_timeline(c)
    touched_keys: set[str] = set()

    for spec in CSCA_TIMELINE_SPECS:
        marker = spec["marker"]
        existing = _find_csca_item(db, student_id, user_id, marker, spec["title"])
        real = parse_real_date(c.get(spec["date_field"])) if active else None
        source = c.get(spec["source_field"]) or ""

        if not real:
            if existing:
                db.delete(existing)
                removed.append(spec["key"])
            continue

        note = f"{marker} source={source or 'student'}"
        if existing:
            existing.deadline = real
            existing.title = spec["title"]
            existing.description = spec["description"]
            existing.student_note = note
            existing.is_manual = True
            existing.updated_at = datetime.utcnow()
            if existing.status not in ("COMPLETED", "NOT_APPLICABLE", "IN_PROGRESS"):
                existing.status = "NOT_STARTED"
            db.add(existing)
            updated.append(spec["key"])
            item = existing
        else:
            item = StudentTimelineItem(
                student_id=student_id,
                user_id=user_id,
                tenant_id=tenant_id,
                title=spec["title"],
                description=spec["description"],
                deadline=real,
                student_note=note,
                is_manual=True,
                status="NOT_STARTED",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(item)
            db.flush()
            created.append(spec["key"])

        touched_keys.add(spec["key"])
        rows = generate_for_timeline_item(db, item, commit=False)
        notified.append(
            {"key": spec["key"], "notifications": len(rows), "deadline": real.isoformat()}
        )

    if not active:
        for spec in CSCA_TIMELINE_SPECS:
            if spec["key"] in touched_keys or spec["key"] in removed:
                continue
            existing = _find_csca_item(db, student_id, user_id, spec["marker"], spec["title"])
            if existing:
                db.delete(existing)
                removed.append(spec["key"])

    if commit:
        db.commit()
    return {
        "created": created,
        "updated": updated,
        "removed": removed,
        "notified": notified,
        "timeline_eligible": active,
        "fake_date_allowed": False,
    }
