"""Personalized Student Timeline — derived from public AdmissionSchedule + profile.

Never mutates AdmissionSchedule / university catalog source rows.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from ..models import AdmissionSchedule, StudentTimelineItem, University
from .student_profile import normalize_profile

TIMELINE_STATUSES = [
    "NOT_STARTED",
    "IN_PROGRESS",
    "COMPLETED",
    "OVERDUE",
    "NOT_APPLICABLE",
]


def _parse_year(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    m = re.search(r"(20\d{2})", text)
    return int(m.group(1)) if m else None


def _end_of_month(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


def infer_deadline(year: int | None, month: int | None, material_deadline: str = "", registration_time: str = "") -> date | None:
    """Best-effort deadline from year/month. Returns None when insufficient."""
    if not year or not month:
        return None
    try:
        y = int(year)
        m = int(month)
        if m < 1 or m > 12:
            return None
        return _end_of_month(y, m)
    except Exception:
        return None


def days_until(deadline: date | None, today: date | None = None) -> int | None:
    if not deadline:
        return None
    today = today or date.today()
    return (deadline - today).days


def compute_status(item: dict | StudentTimelineItem, today: date | None = None) -> str:
    today = today or date.today()
    status = getattr(item, "status", None) if not isinstance(item, dict) else item.get("status")
    if status in ("COMPLETED", "NOT_APPLICABLE", "IN_PROGRESS"):
        return status
    deadline = getattr(item, "deadline", None) if not isinstance(item, dict) else item.get("deadline")
    if isinstance(deadline, str) and deadline:
        try:
            deadline = date.fromisoformat(deadline[:10])
        except ValueError:
            deadline = None
    if deadline and deadline < today and status != "COMPLETED":
        return "OVERDUE"
    return status or "NOT_STARTED"


def serialize_item(row: StudentTimelineItem, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    status = compute_status(row, today)
    deadline = row.deadline
    dtu = days_until(deadline, today)
    return {
        "id": row.id,
        "student_id": row.student_id,
        "source_timeline_id": row.source_timeline_id,
        "title": row.title,
        "description": row.description,
        "start_date": row.start_date.isoformat() if row.start_date else None,
        "deadline": deadline.isoformat() if deadline else None,
        "university_id": row.university_id,
        "university_name": row.university_name,
        "entry_year": row.entry_year,
        "application_route": row.application_route,
        "status": status,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "student_note": row.student_note or "",
        "is_manual": bool(row.is_manual),
        "needs_confirmation": bool(row.needs_confirmation),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "days_until_deadline": dtu,
        "has_precise_deadline": deadline is not None,
    }


def match_public_schedules(db: Session, profile: dict) -> list[dict[str, Any]]:
    """Read-only match of AdmissionSchedule rows to student targets."""
    p = normalize_profile(profile)
    targets = p["goals"]["targets"]
    entry_year = _parse_year(p["basic_info"].get("intended_entry_year"))
    target_years = {_parse_year(t.get("entry_year")) for t in targets}
    target_years = {y for y in target_years if y}
    if entry_year:
        target_years.add(entry_year)

    names = [t.get("university_name") for t in targets if t.get("university_name")]
    routes = set()
    for t in targets:
        route = (t.get("application_route") or "").strip().lower()
        if route:
            routes.add(route)
    intl = p["identity"]["international"]["status"]
    hq = p["identity"]["huaqiao"]["status"]
    if intl not in ("NOT_ASSESSED",):
        routes.add("international")
    if hq not in ("NOT_ASSESSED",):
        routes.add("huaqiao")

    if not names:
        return []

    universities = db.query(University).filter(University.name.in_(names)).all()
    by_name = {u.name: u for u in universities}
    if not by_name:
        # Keep placeholders marked needs_confirmation rather than inventing dates.
        return [
            {
                "source_timeline_id": None,
                "title": f"关注 {name} 官方招生节点",
                "description": "大学库中暂未精确匹配到该校公共时间轴，请人工确认官方简章。",
                "start_date": None,
                "deadline": None,
                "university_id": None,
                "university_name": name,
                "entry_year": entry_year,
                "application_route": "",
                "needs_confirmation": True,
            }
            for name in names
        ]

    uni_ids = [u.id for u in by_name.values()]
    schedules = db.query(AdmissionSchedule).filter(AdmissionSchedule.university_id.in_(uni_ids)).all()
    matched = []
    for s in schedules:
        uni = next((u for u in by_name.values() if u.id == s.university_id), None)
        if not uni:
            continue
        needs = False
        if target_years and s.year not in target_years:
            # If year mismatches but month exists, keep with confirmation flag.
            needs = True
            if entry_year and abs(int(s.year) - entry_year) > 1:
                continue
        reminder = (s.reminder or "") + (s.registration_time or "")
        route = ""
        if "国际生" in reminder:
            route = "international"
        elif "华侨生" in reminder or "联招" in reminder:
            route = "huaqiao"
        if routes and route and route not in routes:
            needs = True
        deadline = infer_deadline(s.year, s.month, s.material_deadline, s.registration_time)
        title = s.registration_time or s.exam_time or f"{uni.name} 招生节点"
        matched.append(
            {
                "source_timeline_id": s.id,
                "title": title,
                "description": s.reminder or f"材料截止：{s.material_deadline}；考试/审核：{s.exam_time}",
                "start_date": date(s.year, s.month, 1) if s.year and s.month else None,
                "deadline": deadline,
                "university_id": uni.id,
                "university_name": uni.name,
                "entry_year": entry_year or s.year,
                "application_route": route,
                "needs_confirmation": needs or deadline is None,
            }
        )
    return matched


def regenerate_student_timeline(db: Session, student_id: int, user_id: int, tenant_id: int, profile: dict) -> list[StudentTimelineItem]:
    """Rebuild derived items while preserving COMPLETED / notes / manual rows."""
    existing = (
        db.query(StudentTimelineItem)
        .filter(StudentTimelineItem.student_id == student_id, StudentTimelineItem.user_id == user_id)
        .all()
    )
    by_source: dict[int, StudentTimelineItem] = {}
    manuals = []
    for row in existing:
        if row.is_manual:
            manuals.append(row)
        elif row.source_timeline_id is not None:
            by_source[row.source_timeline_id] = row

    matched = match_public_schedules(db, profile)
    keep_source_ids = set()
    now = datetime.utcnow()
    for item in matched:
        sid = item.get("source_timeline_id")
        if sid is None:
            # Placeholder without source id: create/update by university_name+title
            row = next(
                (
                    r
                    for r in existing
                    if not r.is_manual
                    and r.source_timeline_id is None
                    and r.university_name == item["university_name"]
                    and r.title == item["title"]
                ),
                None,
            )
            if not row:
                row = StudentTimelineItem(student_id=student_id, user_id=user_id, tenant_id=tenant_id, is_manual=False)
                db.add(row)
            if row.status not in ("COMPLETED", "IN_PROGRESS"):
                row.status = "NOT_STARTED"
            # preserve note / completed
        else:
            keep_source_ids.add(sid)
            row = by_source.get(sid)
            if not row:
                row = StudentTimelineItem(
                    student_id=student_id,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    source_timeline_id=sid,
                    is_manual=False,
                    status="NOT_STARTED",
                )
                db.add(row)
            else:
                # preserve completed / notes
                pass
        row.title = item["title"]
        row.description = item.get("description") or ""
        row.start_date = item.get("start_date")
        row.deadline = item.get("deadline")
        row.university_id = item.get("university_id")
        row.university_name = item.get("university_name") or ""
        row.entry_year = item.get("entry_year")
        row.application_route = item.get("application_route") or ""
        row.needs_confirmation = bool(item.get("needs_confirmation"))
        row.updated_at = now
        if row.status not in ("COMPLETED", "IN_PROGRESS", "NOT_APPLICABLE"):
            row.status = compute_status(row)

    # Mark unmatched previous derived rows as NOT_APPLICABLE (do not delete completed history)
    for sid, row in by_source.items():
        if sid not in keep_source_ids:
            if row.status == "COMPLETED":
                row.status = "COMPLETED"
                row.needs_confirmation = True
                row.description = (row.description or "") + "\n（该节点可能已不再匹配当前目标，请确认）"
            else:
                row.status = "NOT_APPLICABLE"
            row.updated_at = now

    db.commit()
    rows = (
        db.query(StudentTimelineItem)
        .filter(StudentTimelineItem.student_id == student_id, StudentTimelineItem.user_id == user_id)
        .all()
    )
    rows.sort(key=lambda r: ((r.deadline or date.max), r.id or 0))
    return rows


def timeline_summary(items: list[dict[str, Any]], today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    overdue = []
    next30 = []
    next90 = []
    for it in items:
        status = it.get("status")
        if status == "NOT_APPLICABLE":
            continue
        if status == "OVERDUE" or (it.get("days_until_deadline") is not None and it["days_until_deadline"] < 0 and status != "COMPLETED"):
            overdue.append(it)
            continue
        if status == "COMPLETED":
            continue
        dtu = it.get("days_until_deadline")
        if dtu is None:
            continue
        if 0 <= dtu <= 30:
            next30.append(it)
        elif 30 < dtu <= 90:
            next90.append(it)
    return {
        "overdue_count": len(overdue),
        "next_30_count": len(next30),
        "next_90_count": len(next90),
        "next_30": next30[:5],
        "next_90": next90[:5],
        "overdue": overdue[:5],
    }


def group_timeline(items: list[dict[str, Any]]) -> dict[str, list]:
    groups = {"overdue": [], "next_30": [], "next_90": [], "later": [], "completed": []}
    for it in items:
        status = it.get("status")
        if status == "COMPLETED":
            groups["completed"].append(it)
            continue
        if status == "NOT_APPLICABLE":
            groups["later"].append(it)
            continue
        dtu = it.get("days_until_deadline")
        if status == "OVERDUE" or (dtu is not None and dtu < 0):
            groups["overdue"].append(it)
        elif dtu is not None and dtu <= 30:
            groups["next_30"].append(it)
        elif dtu is not None and dtu <= 90:
            groups["next_90"].append(it)
        else:
            groups["later"].append(it)
    return groups
