"""Admin console RBAC abstraction (V1).

Current DB roles: admin | member.
Proposed console roles: super_admin | consultant | support.

This module maps existing `users.role == "admin"` → super_admin for login,
and exposes capability checks for future consultant/support without breaking
`require_admin`.
"""
from __future__ import annotations

from enum import Enum
from typing import Iterable

from fastapi import Depends, HTTPException

from ..models import User
from .security import get_current_user, require_admin


class AdminConsoleRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    CONSULTANT = "consultant"
    SUPPORT = "support"


# Capability matrix (proposal + V1 enforcement where roles exist).
ROLE_CAPABILITIES: dict[AdminConsoleRole, frozenset[str]] = {
    AdminConsoleRole.SUPER_ADMIN: frozenset(
        {
            "admin.login",
            "admin.dashboard",
            "admin.users.read",
            "admin.students.read",
            "admin.student360.read",
            "admin.student360.write",
            "admin.ai.generate",
            "admin.ai.edit",
            "admin.ai.approve",
            "admin.ai.publish",
            "admin.sensitive.unmask",  # future — V1 still masks by default
            "admin.settings",
        }
    ),
    AdminConsoleRole.CONSULTANT: frozenset(
        {
            "admin.login",
            "admin.dashboard",
            "admin.students.read",  # assigned only — future filter
            "admin.student360.read",
            "admin.student360.write",
            "admin.ai.generate",
            "admin.ai.edit",
            "admin.ai.approve",
            "admin.ai.publish",
        }
    ),
    AdminConsoleRole.SUPPORT: frozenset(
        {
            "admin.login",
            "admin.dashboard",
            "admin.users.read",
            # no full student archive / no AI publish
        }
    ),
}


def resolve_console_role(user: User) -> AdminConsoleRole | None:
    """Map DB user.role → console role. V1: only admin → super_admin."""
    role = (user.role or "").strip().lower()
    if role == "admin":
        return AdminConsoleRole.SUPER_ADMIN
    # Future: role in {"consultant", "support", "super_admin"} after migration.
    if role == "super_admin":
        return AdminConsoleRole.SUPER_ADMIN
    if role == "consultant":
        return AdminConsoleRole.CONSULTANT
    if role == "support":
        return AdminConsoleRole.SUPPORT
    return None


def can_login_admin(user: User) -> bool:
    console = resolve_console_role(user)
    if console is None:
        return False
    return "admin.login" in ROLE_CAPABILITIES[console]


def has_capability(user: User, capability: str) -> bool:
    console = resolve_console_role(user)
    if console is None:
        return False
    return capability in ROLE_CAPABILITIES[console]


def require_admin_console(user: User = Depends(get_current_user)) -> User:
    """JWT-authenticated user allowed into Admin Console.

    V1: preserves require_admin semantics (role == admin) while routing through
    the console role abstraction for future consultant/support.
    """
    if not can_login_admin(user):
        # Keep message compatible with existing admin gate for admin-only V1.
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def require_capability(capability: str):
    def _dep(user: User = Depends(require_admin_console)) -> User:
        if not has_capability(user, capability):
            raise HTTPException(status_code=403, detail=f"缺少权限: {capability}")
        return user

    return _dep


def rbac_proposal() -> dict:
    return {
        "current_db_roles": ["admin", "member"],
        "proposed_console_roles": [r.value for r in AdminConsoleRole],
        "v1_mapping": {"admin": "super_admin"},
        "capabilities": {r.value: sorted(caps) for r, caps in ROLE_CAPABILITIES.items()},
        "migration_required_for": ["consultant", "support"],
        "note": "Do not break require_admin; extend via users.role values + optional assignment table.",
    }


# Re-export for callers that still want classic gate alongside console.
__all__ = [
    "AdminConsoleRole",
    "ROLE_CAPABILITIES",
    "resolve_console_role",
    "can_login_admin",
    "has_capability",
    "require_admin_console",
    "require_capability",
    "rbac_proposal",
    "require_admin",
]
