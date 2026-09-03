"""Student profile seat/slot entitlements.

Priority:
  account override (user.student_profile_limit_override)
  > membership plan entitlement
  > default FREE limit

ACTIVE / ARCHIVED / DELETED all consume seats (soft-deleted cannot bypass limits).
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import StudentMasterProfile, User

# Plan defaults — do not hardcode "3" at call sites.
FREE_STUDENT_PROFILE_LIMIT = 1
PRO_STUDENT_PROFILE_LIMIT = 3
FAMILY_PLUS_STUDENT_PROFILE_LIMIT = 5
CONSULTANT_20_STUDENT_PROFILE_LIMIT = 20
CONSULTANT_50_STUDENT_PROFILE_LIMIT = 50
ENTERPRISE_STUDENT_PROFILE_LIMIT = 100

# Reserved / current plan codes → student_profile_limit
PLAN_STUDENT_PROFILE_LIMITS: dict[str, int] = {
    "free": FREE_STUDENT_PROFILE_LIMIT,
    # Current SaaS paid plans (seed) — PRO family seat = 3
    "vip_month": PRO_STUDENT_PROFILE_LIMIT,
    "vip_year": PRO_STUDENT_PROFILE_LIMIT,
    "vip_three_year": PRO_STUDENT_PROFILE_LIMIT,
    "lifetime": PRO_STUDENT_PROFILE_LIMIT,
    "monthly": PRO_STUDENT_PROFILE_LIMIT,
    "yearly": PRO_STUDENT_PROFILE_LIMIT,
    # Alternate / test plan codes used by is_paid()
    "pro_monthly": PRO_STUDENT_PROFILE_LIMIT,
    "pro_yearly": PRO_STUDENT_PROFILE_LIMIT,
    "pro_plus_yearly": PRO_STUDENT_PROFILE_LIMIT,
    # Reserved commercial tiers (not required in UI this round)
    "family_plus": FAMILY_PLUS_STUDENT_PROFILE_LIMIT,
    "consultant_20": CONSULTANT_20_STUDENT_PROFILE_LIMIT,
    "consultant_50": CONSULTANT_50_STUDENT_PROFILE_LIMIT,
    "enterprise": ENTERPRISE_STUDENT_PROFILE_LIMIT,
}

STUDENT_PROFILE_STATUSES = ("ACTIVE", "ARCHIVED", "DELETED")
# All statuses consume a seat for the current billing-cycle-safe rule.
SEAT_CONSUMING_STATUSES = ("ACTIVE", "ARCHIVED", "DELETED")

LIMIT_REACHED_CODE = "STUDENT_PROFILE_LIMIT_REACHED"


def plan_student_profile_limit(plan_code: str | None) -> int:
    code = (plan_code or "free").strip().lower() or "free"
    if code in PLAN_STUDENT_PROFILE_LIMITS:
        return PLAN_STUDENT_PROFILE_LIMITS[code]
    # Unknown paid-looking codes fall back to PRO seats; otherwise FREE.
    if code not in ("free", ""):
        return PRO_STUDENT_PROFILE_LIMIT
    return FREE_STUDENT_PROFILE_LIMIT


class StudentProfileEntitlementService:
    """Single source of truth for student profile seat limits."""

    def resolve_limit(self, user: User) -> int:
        override = getattr(user, "student_profile_limit_override", None)
        if override is not None:
            try:
                value = int(override)
                if value >= 0:
                    return value
            except (TypeError, ValueError):
                pass
        return plan_student_profile_limit(user.plan_code)

    def count_used(self, db: Session, user: User) -> int:
        """Count profiles that consume seats (ACTIVE + ARCHIVED + DELETED)."""
        q = db.query(StudentMasterProfile).filter(StudentMasterProfile.user_id == user.id)
        # Backward compatible: rows without status column default treated as ACTIVE via model default.
        return q.count()

    def usage(self, db: Session, user: User) -> dict[str, Any]:
        limit = self.resolve_limit(user)
        used = self.count_used(db, user)
        remaining = max(0, limit - used)
        over_quota = max(0, used - limit)
        return {
            "student_profile_limit": limit,
            "student_profile_used": used,
            "student_profile_remaining": remaining,
            "student_profile_over_quota": over_quota,
            "can_create_student": used < limit,
            "limit_source": (
                "account_override"
                if getattr(user, "student_profile_limit_override", None) is not None
                else "membership_plan"
            ),
            "plan_code": user.plan_code,
        }

    def assert_can_create(self, db: Session, user: User) -> dict[str, Any]:
        info = self.usage(db, user)
        if not info["can_create_student"]:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": LIMIT_REACHED_CODE,
                    "limit": info["student_profile_limit"],
                    "used": info["student_profile_used"],
                    "remaining": info["student_profile_remaining"],
                    "message": (
                        f"当前套餐最多可建立 {info['student_profile_limit']} 个学生档案，"
                        f"已使用 {info['student_profile_used']}/{info['student_profile_limit']}。"
                        "如需管理更多学生，请升级套餐。"
                    ),
                },
            )
        return info


student_profile_entitlements = StudentProfileEntitlementService()
