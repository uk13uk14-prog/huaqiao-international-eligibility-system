from .security import has_smart_timeline, is_paid

FREE_LIMITS = {
    "university_limit": 8,
    "recommend_limit": 3,
    "record_limit": 20,
    "report_export": False,
}
PAID_LIMITS = {
    "university_limit": 999,
    "recommend_limit": 12,
    "record_limit": 9999,
    "report_export": True,
}


def entitlements(user):
    return PAID_LIMITS if is_paid(user) else FREE_LIMITS


def feature_summary(user):
    paid = is_paid(user)
    smart_timeline = has_smart_timeline(user)
    return {
        "plan_code": user.plan_code,
        "paid": paid,
        "membership_until": user.membership_until.isoformat() if user.membership_until else None,
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
    }
