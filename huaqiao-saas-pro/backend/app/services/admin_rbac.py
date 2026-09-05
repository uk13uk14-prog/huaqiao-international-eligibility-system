"""Admin Console V2 RBAC — backend-enforced capabilities.

Reuses users.role. Legacy `admin` maps to SUPER_ADMIN.
Customers (member / account_kind=CUSTOMER) cannot log into the console.
"""
from __future__ import annotations

from enum import Enum

from fastapi import Depends, HTTPException

from ..models import User
from .security import get_current_user, require_admin


class AdminConsoleRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    OPERATIONS_ADMIN = "operations_admin"
    CONSULTANT = "consultant"
    SUPPORT = "support"


# Canonical capability ids (V2). Old admin.* aliases still accepted.
ALL_CAPABILITIES = frozenset(
    {
        "dashboard.read",
        "users.read",
        "users.write",
        "students.read",
        "students.write",
        "students.assign",
        "student360.read",
        "student360.write",
        "followups.read",
        "followups.write",
        "consultations.read",
        "consultations.write",
        "employees.read",
        "employees.write",
        "consultants.read",
        "consultants.write",
        "roles.read",
        "roles.write",
        "ai.generate",
        "ai.review",
        "ai.publish",
        "audit.read",
        "settings.read",
        "settings.write",
        "admin.login",
    }
)

# Backward-compatible aliases used by existing V1 routes
_ALIAS = {
    "admin.dashboard": "dashboard.read",
    "admin.users.read": "users.read",
    "admin.students.read": "students.read",
    "admin.student360.read": "student360.read",
    "admin.student360.write": "student360.write",
    "admin.ai.generate": "ai.generate",
    "admin.ai.edit": "ai.generate",
    "admin.ai.approve": "ai.review",
    "admin.ai.publish": "ai.publish",
    "admin.settings": "settings.write",
    "admin.sensitive.unmask": "settings.write",
}

ROLE_CAPABILITIES: dict[AdminConsoleRole, frozenset[str]] = {
    AdminConsoleRole.SUPER_ADMIN: ALL_CAPABILITIES,
    AdminConsoleRole.OPERATIONS_ADMIN: frozenset(
        {
            "admin.login",
            "dashboard.read",
            "users.read",
            "users.write",
            "students.read",
            "students.write",
            "students.assign",
            "student360.read",
            "student360.write",
            "followups.read",
            "followups.write",
            "consultations.read",
            "consultations.write",
            "employees.read",
            "consultants.read",
            "consultants.write",
            "roles.read",
            "ai.generate",
            "ai.review",
            "ai.publish",
            "audit.read",
            "settings.read",
        }
    ),
    AdminConsoleRole.CONSULTANT: frozenset(
        {
            "admin.login",
            "dashboard.read",
            "students.read",
            "students.write",
            "student360.read",
            "student360.write",
            "followups.read",
            "followups.write",
            "consultations.read",
            "consultations.write",
            "consultants.read",
            "ai.generate",
        }
    ),
    AdminConsoleRole.SUPPORT: frozenset(
        {
            "admin.login",
            "dashboard.read",
            "users.read",
            "students.read",
            "student360.read",
            "followups.read",
            "followups.write",
            "consultations.read",
            "consultations.write",
        }
    ),
}

STAFF_DB_ROLES = frozenset(
    {"admin", "super_admin", "operations_admin", "consultant", "support"}
)
ASSIGNABLE_DB_ROLES = frozenset(
    {"admin", "super_admin", "operations_admin", "consultant"}
)
CUSTOMER_DB_ROLES = frozenset({"member", "user"})

ROLE_LABEL_ZH = {
    "super_admin": "超级管理员",
    "operations_admin": "运营管理员",
    "consultant": "顾问",
    "support": "客服",
    "admin": "超级管理员",
}

JOB_TITLE_PRESETS = ("升学顾问", "高级升学顾问", "客服", "运营", "管理员")


def canonical_capability(capability: str) -> str:
    return _ALIAS.get(capability, capability)


def resolve_console_role(user: User) -> AdminConsoleRole | None:
    role = (user.role or "").strip().lower()
    if role in {"admin", "super_admin"}:
        return AdminConsoleRole.SUPER_ADMIN
    if role == "operations_admin":
        return AdminConsoleRole.OPERATIONS_ADMIN
    if role == "consultant":
        return AdminConsoleRole.CONSULTANT
    if role == "support":
        return AdminConsoleRole.SUPPORT
    return None


def is_staff_account(user: User) -> bool:
    kind = (getattr(user, "account_kind", None) or "").upper()
    if kind == "STAFF":
        return True
    if kind == "CUSTOMER":
        return (user.role or "").lower() in STAFF_DB_ROLES
    return (user.role or "").lower() in STAFF_DB_ROLES


def is_customer_account(user: User) -> bool:
    return not is_staff_account(user)


def can_login_admin(user: User) -> bool:
    if not getattr(user, "is_active", True):
        return False
    if not is_staff_account(user):
        return False
    console = resolve_console_role(user)
    if console is None:
        return False
    return "admin.login" in ROLE_CAPABILITIES[console]


def capabilities_for(user: User) -> list[str]:
    console = resolve_console_role(user)
    if console is None:
        return []
    return sorted(ROLE_CAPABILITIES[console])


def has_capability(user: User, capability: str) -> bool:
    cap = canonical_capability(capability)
    console = resolve_console_role(user)
    if console is None:
        return False
    granted = ROLE_CAPABILITIES[console]
    return cap in granted or capability in granted


def require_admin_console(user: User = Depends(get_current_user)) -> User:
    if not can_login_admin(user):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def require_capability(capability: str):
    def _dep(user: User = Depends(require_admin_console)) -> User:
        if not has_capability(user, capability):
            raise HTTPException(status_code=403, detail=f"缺少权限: {canonical_capability(capability)}")
        return user

    return _dep


def consultant_scoped(user: User) -> bool:
    return resolve_console_role(user) == AdminConsoleRole.CONSULTANT


def rbac_proposal() -> dict:
    return {
        "version": "v2",
        "current_db_roles": ["admin", "member", "super_admin", "operations_admin", "consultant", "support"],
        "console_roles": [r.value for r in AdminConsoleRole],
        "role_labels": ROLE_LABEL_ZH,
        "v1_mapping": {"admin": "super_admin"},
        "capabilities": {r.value: sorted(caps) for r, caps in ROLE_CAPABILITIES.items()},
        "staff_customer_separation": True,
        "note": "Backend enforces capabilities. Frontend menus are derived from /me.permissions.",
    }


def menu_for(user: User) -> list[dict]:
    """Role-derived navigation. Frontend hides items; backend still enforces."""
    caps = set(capabilities_for(user))
    role = resolve_console_role(user)
    items: list[dict] = []

    def add(group: str, path: str, title: str, need: str | None = None, *, consultant_only=False, hide_for_consultant=False):
        if consultant_only and role != AdminConsoleRole.CONSULTANT:
            return
        if hide_for_consultant and role == AdminConsoleRole.CONSULTANT:
            return
        if need and need not in caps and canonical_capability(need) not in caps:
            return
        items.append({"group": group, "path": path, "title": title})

    add("工作台", "/dashboard", "工作台", "dashboard.read")
    add("客户与学生", "/users", "用户管理", "users.read", hide_for_consultant=True)
    add("客户与学生", "/students", "学生管理", "students.read", hide_for_consultant=True)
    add("客户与学生", "/my-students", "我的学生", "students.read", consultant_only=True)
    add("客户与学生", "/consultations", "咨询管理", "consultations.read")
    add("运营 CRM", "/my-students", "我的学生", "students.read")
    add("运营 CRM", "/follow-ups", "待跟进", "followups.read")
    add("运营 CRM", "/tasks/today", "今日任务", "followups.read")
    add("运营 CRM", "/tasks/overdue", "逾期任务", "followups.read")
    add("员工与组织", "/employees", "员工管理", "employees.read")
    add("员工与组织", "/consultants", "顾问管理", "consultants.read")
    add("员工与组织", "/roles", "角色管理", "roles.read")
    add("员工与组织", "/audit", "操作日志", "audit.read")
    add("AI 中心", "/ai/queue", "AI 审核队列", "ai.review")
    add("AI 中心", "/m/ai", "AI 助手", "ai.generate")
    add("系统", "/settings", "系统设置", "settings.read")
    if "settings.write" in caps:
        add("系统", "/settings", "系统设置", "settings.write")
    # de-dupe paths keeping first
    seen = set()
    out = []
    for it in items:
        key = (it["group"], it["path"])
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


__all__ = [
    "AdminConsoleRole",
    "ROLE_CAPABILITIES",
    "ALL_CAPABILITIES",
    "STAFF_DB_ROLES",
    "ASSIGNABLE_DB_ROLES",
    "ROLE_LABEL_ZH",
    "JOB_TITLE_PRESETS",
    "resolve_console_role",
    "can_login_admin",
    "has_capability",
    "require_admin_console",
    "require_capability",
    "rbac_proposal",
    "require_admin",
    "is_staff_account",
    "is_customer_account",
    "capabilities_for",
    "consultant_scoped",
    "menu_for",
    "canonical_capability",
]
