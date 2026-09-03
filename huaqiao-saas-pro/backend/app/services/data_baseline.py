"""Authoritative data-baseline metrics for university catalog + admission timelines.

Historical acceptance used:
- UNIVERSITY_COUNT = 125  → seeded DB (core catalog 122 + FREE_UNIVERSITIES 3)
- TIMELINE = 313          → stale/misclassified figure; NOT template count (11)
  and NOT current expanded AdmissionSchedule count (900 after fresh seed).

This module never invents universities or schedule rows.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..models import AdmissionSchedule, University
from ..seed import FREE_UNIVERSITIES, schedules_for
from .university_catalog import (
    DEFAULT_SCHEDULES,
    EXTRA_UNIVERSITIES,
    FIELD_SCHEDULES,
    PROJECT_985,
    PURE_211,
    UNIVERSITIES,
)

# Explicit aliases only — keep empty unless a real synonym must resolve to catalog/DB name.
# Do not hardcode aliases in Vue.
UNIVERSITY_NAME_ALIASES: dict[str, str] = {
    # Examples reserved for future verified aliases:
    # "北大": "北京大学",
}

EXPECTED_CATALOG_RAW_COUNT = len(PROJECT_985) + len(PURE_211) + len(EXTRA_UNIVERSITIES)  # 122
EXPECTED_CATALOG_UNIQUE_COUNT = 122
EXPECTED_FREE_UNIVERSITY_COUNT = 3
EXPECTED_SEEDED_UNIVERSITY_COUNT = 125  # historical baseline
EXPECTED_TIMELINE_TEMPLATE_COUNT = len(DEFAULT_SCHEDULES) + sum(len(v) for v in FIELD_SCHEDULES.values())  # 11
FREE_UNIVERSITY_NAMES = tuple(item["name"] for item in FREE_UNIVERSITIES)


def canonicalize_university_name(name: str) -> str:
    text = (name or "").strip()
    if not text:
        return ""
    return UNIVERSITY_NAME_ALIASES.get(text, text)


def catalog_metrics() -> dict[str, Any]:
    names = [u["name"] for u in UNIVERSITIES]
    return {
        "project_985_count": len(PROJECT_985),
        "pure_211_count": len(PURE_211),
        "extra_count": len(EXTRA_UNIVERSITIES),
        "source_raw_count": len(PROJECT_985) + len(PURE_211) + len(EXTRA_UNIVERSITIES),
        "unique_name_count": len(set(names)),
        "catalog_count": len(UNIVERSITIES),
        "free_university_names": list(FREE_UNIVERSITY_NAMES),
        "free_university_count": len(FREE_UNIVERSITY_NAMES),
        "seeded_expected_count": len(set(names) | set(FREE_UNIVERSITY_NAMES)),
        "historical_baseline": EXPECTED_SEEDED_UNIVERSITY_COUNT,
        "missing_vs_historical_baseline_if_catalog_only": list(FREE_UNIVERSITY_NAMES),
        "root_cause": (
            "Previous report counted UNIVERSITIES catalog only (122). "
            "Historical 125 baseline is seeded DB = catalog 122 + FREE_UNIVERSITIES 3 "
            f"({', '.join(FREE_UNIVERSITY_NAMES)})."
        ),
    }


def expected_seeded_schedule_count() -> int:
    total = 0
    for item in list(UNIVERSITIES) + list(FREE_UNIVERSITIES):
        total += len(schedules_for(item["fields"]))
    return total


def timeline_template_metrics() -> dict[str, Any]:
    field_rows = sum(len(v) for v in FIELD_SCHEDULES.values())
    return {
        "default_template_count": len(DEFAULT_SCHEDULES),
        "field_template_count": field_rows,
        "timeline_template_count": len(DEFAULT_SCHEDULES) + field_rows,
        "expected_admission_schedule_count_after_seed": expected_seeded_schedule_count(),
        "historical_313_meaning": (
            "313 is not the template library (11) and does not match current expanded "
            f"AdmissionSchedule count ({expected_seeded_schedule_count()} after fresh seed of 125 universities). "
            "No git/docs source reproduces 313. Treat 313 as a stale acceptance label; "
            "authoritative metrics are TIMELINE_TEMPLATE_COUNT and ADMISSION_SCHEDULE_COUNT."
        ),
    }


def db_university_metrics(db: Session) -> dict[str, Any]:
    rows = db.query(University).all()
    names = [u.name for u in rows]
    return {
        "db_count": len(rows),
        "db_unique_name_count": len(set(names)),
        "names": sorted(set(names)),
    }


def db_schedule_metrics(db: Session) -> dict[str, Any]:
    total = db.query(AdmissionSchedule).count()
    uni_ids = {row.university_id for row in db.query(AdmissionSchedule.university_id).distinct()}
    return {
        "admission_schedule_count": total,
        "university_timeline_coverage": len(uni_ids),
        "generated_timeline_node_count": total,  # seed writes 1 node per schedule row
    }


def resolve_university(db: Session, name: str) -> University | None:
    canon = canonicalize_university_name(name)
    if not canon:
        return None
    return db.query(University).filter(University.name == canon).first()


def resolve_targets(db: Session, targets: list[dict]) -> dict[str, Any]:
    """Ensure target university names resolve to DB catalog IDs with consistent names."""
    resolved = []
    unresolved = []
    for t in targets:
        raw = t.get("university_name") or ""
        uni = resolve_university(db, raw)
        if not uni:
            unresolved.append({"university_name": raw, "reason": "NOT_IN_UNIVERSITY_DB"})
            continue
        row = dict(t)
        row["university_id"] = uni.id
        row["university_name"] = uni.name  # canonicalize to DB name
        resolved.append(row)
    return {"resolved": resolved, "unresolved": unresolved}
