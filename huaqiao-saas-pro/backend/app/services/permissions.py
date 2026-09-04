from .security import has_smart_timeline, is_paid, trial_info
from .student_profile_entitlements import (
    FREE_STUDENT_PROFILE_LIMIT,
    PRO_STUDENT_PROFILE_LIMIT,
    student_profile_entitlements,
)

FREE_LIMITS = {
    "university_limit": 8,
    "recommend_limit": 3,
    "record_limit": 20,
    "report_export": False,
    "student_profile_limit": FREE_STUDENT_PROFILE_LIMIT,
}
PAID_LIMITS = {
    "university_limit": 999,
    "recommend_limit": 12,
    "record_limit": 9999,
    "report_export": True,
    "student_profile_limit": PRO_STUDENT_PROFILE_LIMIT,
}


def entitlements(user, db=None):
    """Membership entitlements. When db is provided, include live student seat usage."""
    base = dict(PAID_LIMITS if is_paid(user) else FREE_LIMITS)
    # Always resolve student_profile_limit via dedicated service (plan + override).
    limit = student_profile_entitlements.resolve_limit(user)
    base["student_profile_limit"] = limit
    if db is not None and user is not None:
        usage = student_profile_entitlements.usage(db, user)
        base.update(usage)
    return base


def feature_summary(user, db=None):
    paid = is_paid(user)
    smart_timeline = has_smart_timeline(user)
    trial = trial_info(user)
    summary = {
        "plan_code": user.plan_code,
        "plan": user.plan_code,
        "paid": paid,
        "is_pro": paid,
        "membership_until": user.membership_until.isoformat() if user.membership_until else None,
        "trial_status": trial["trial_status"],
        "trial_active": trial["trial_active"],
        "trial_started_at": trial["trial_started_at"],
        "trial_ends_at": trial["trial_ends_at"],
        "trial_days_remaining": trial["trial_days_remaining"],
        "international_focus": True,
        "full_elite_university_library": paid,
        "art_sport_specialty": paid,
        "international_planning": paid,
        "report_export": paid,
        "unlimited_recommendations": paid,
        "permanent_history": paid,
        "one_on_one_expert": paid,
        "custom_expert_report": paid,
        "full_timeline_reminders": smart_timeline,
        "customer_vault_cloud": paid,
        "student_profile_limit": student_profile_entitlements.resolve_limit(user),
    }
    if db is not None:
        usage = student_profile_entitlements.usage(db, user)
        summary.update(
            {
                "student_profile_limit": usage["student_profile_limit"],
                "student_profile_used": usage["student_profile_used"],
                "student_profile_remaining": usage["student_profile_remaining"],
                "student_profile_over_quota": usage["student_profile_over_quota"],
                "can_create_student": usage["can_create_student"],
            }
        )
    return summary
