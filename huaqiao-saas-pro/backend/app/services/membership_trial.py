"""7-day Pro Trial helpers — server-side only (no client clock trust).

Reuses User.plan_code + User.membership_until (no schema migration).
New registrations get plan_code=pro_trial and membership_until=now+7d.
Existing users are never auto-migrated into trial.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

TRIAL_DAYS = 7
TRIAL_PLAN_CODE = "pro_trial"

# Production VIP plans (seed) + legacy test codes + trial
VIP_PAID_PLANS = {
    "vip_month",
    "vip_year",
    "vip_three_year",
    "monthly",
    "yearly",
}
LEGACY_TEST_PAID_PLANS = {
    "pro_monthly",
    "pro_yearly",
    "pro_plus_yearly",
}
LIFETIME_PLANS = {"lifetime"}
SMART_TIMELINE_PLANS = {
    "vip_year",
    "vip_three_year",
    "lifetime",
    "yearly",
    "pro_plus_yearly",
    "pro_yearly",  # tests historically treated yearly as paid+timeline-capable
}

ALL_MEMBERSHIP_PLANS = (
    VIP_PAID_PLANS | LEGACY_TEST_PAID_PLANS | LIFETIME_PLANS | {TRIAL_PLAN_CODE}
)


def _utcnow() -> datetime:
    return datetime.utcnow()


def _code(user) -> str:
    if not user or not getattr(user, "plan_code", None):
        return "free"
    return str(user.plan_code).strip().lower() or "free"


def is_trial_plan(plan_code: str | None) -> bool:
    return (plan_code or "").strip().lower() == TRIAL_PLAN_CODE


def grant_new_user_pro_trial(user, *, now: datetime | None = None) -> Any:
    """Apply 7-day Pro trial to a brand-new registration only."""
    now = now or _utcnow()
    user.plan_code = TRIAL_PLAN_CODE
    user.membership_until = now + timedelta(days=TRIAL_DAYS)
    return user


def is_paid(user, *, now: datetime | None = None) -> bool:
    """Active Pro / Trial / VIP membership (server clock).

    Existing-user protection:
    - plan_code=free → never paid
    - lifetime → always paid
    - vip_* / pro_* with membership_until=None → treat as active (legacy rows)
    - pro_trial requires membership_until > now
    - expired membership_until → not paid (Free fallback limits apply; data kept)
    """
    now = now or _utcnow()
    code = _code(user)
    if code in ("free", ""):
        return False
    if code in LIFETIME_PLANS:
        return True
    if code not in ALL_MEMBERSHIP_PLANS:
        # Unknown non-free code: do not silently grant Pro; do not invent trial.
        until = getattr(user, "membership_until", None)
        if until is None:
            return False
        return until > now

    until = getattr(user, "membership_until", None)
    if code == TRIAL_PLAN_CODE:
        return until is not None and until > now

    # VIP / legacy paid: null until → protect existing users; else honor expiry
    if until is None:
        return True
    return until > now


def has_smart_timeline(user, *, now: datetime | None = None) -> bool:
    """Year+ / lifetime style timeline reminders (not month trial)."""
    if not is_paid(user, now=now):
        return False
    return _code(user) in SMART_TIMELINE_PLANS


def trial_info(user, *, now: datetime | None = None) -> dict[str, Any]:
    """Entitlement trial block for API / UI (never trust client clock)."""
    now = now or _utcnow()
    code = _code(user)
    until = getattr(user, "membership_until", None)
    created = getattr(user, "created_at", None)

    if code != TRIAL_PLAN_CODE:
        # Paid non-trial
        if is_paid(user, now=now):
            return {
                "trial_status": "PAID",
                "trial_active": False,
                "trial_started_at": None,
                "trial_ends_at": until.isoformat() if until else None,
                "trial_days_remaining": None,
                "is_pro": True,
            }
        return {
            "trial_status": "NONE",
            "trial_active": False,
            "trial_started_at": None,
            "trial_ends_at": None,
            "trial_days_remaining": None,
            "is_pro": False,
        }

    started = None
    if until is not None:
        started = until - timedelta(days=TRIAL_DAYS)
    elif created is not None:
        started = created

    active = until is not None and until > now
    days_remaining = None
    if active and until is not None:
        delta = until - now
        # ceil-ish remaining calendar days for UI badge (at least 1 while active)
        days_remaining = max(1, int(delta.total_seconds() // 86400) + (1 if delta.total_seconds() % 86400 else 0))
        if days_remaining > TRIAL_DAYS:
            days_remaining = TRIAL_DAYS

    return {
        "trial_status": "ACTIVE" if active else "EXPIRED",
        "trial_active": active,
        "trial_started_at": started.isoformat() if started else None,
        "trial_ends_at": until.isoformat() if until else None,
        "trial_days_remaining": days_remaining if active else 0,
        "is_pro": active,
    }
