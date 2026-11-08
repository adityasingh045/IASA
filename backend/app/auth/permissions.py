"""
ISA auth: permissions, user resolution, workspace checks.

Enforcement happens in backend code on every API call — never trust the frontend.
"""
from __future__ import annotations

import enum

from app.database.models import PermissionLevel, WorkspaceRole


class PermissionClass(enum.StrEnum):
    READ = "READ"
    CONTROLLED = "CONTROLLED"
    RESTRICTED = "RESTRICTED"


# ── Permission escalation map ────────────────────────────────────────────────────
# A user with a given role can perform actions at this level or below.
ROLE_PERMISSION_MAP: dict[str, set[PermissionClass]] = {
    WorkspaceRole.ADMIN: {PermissionClass.READ, PermissionClass.CONTROLLED, PermissionClass.RESTRICTED},
    WorkspaceRole.MEMBER: {PermissionClass.READ, PermissionClass.CONTROLLED},
}


def can_perform(role: str, required_permission: str) -> bool:
    """Can a user with `role` perform an action requiring `required_permission`?"""
    allowed = ROLE_PERMISSION_MAP.get(role, {PermissionClass.READ})
    return PermissionClass(required_permission) in allowed


def require_permission(
    user_role: str,
    required_permission: str,
    tool_name: str = "",
) -> None:
    """Raise PermissionDeniedError if the user's role cannot perform the action."""
    if not can_perform(user_role, required_permission):
        from app.core.errors import PermissionDeniedError
        raise PermissionDeniedError(
            message=f"Role '{user_role}' cannot perform '{required_permission}' action",
            tool_name=tool_name,
            permission=required_permission,
        )


def classify_action(action_description: str) -> PermissionClass:
    """
    Heuristic classification of an action description into a permission level.
    Used as a default when a tool doesn't have an explicit permission set.

    READ:     safe, read-only queries
    CONTROLLED: changes with limited operational impact
    RESTRICTED: destructive, sensitive, safety-critical, or device-affecting
    """
    described = action_description.lower()

    if any(word in described for word in [
        "delete", "destroy", "wipe", "remove source", "disable camera",
        "escalate", "trigger", "safety", "device", "shutdown", "emergency",
    ]):
        return PermissionClass.RESTRICTED

    if any(word in described for word in [
        "add", "create", "register", "update", "change", "modify",
        "review", "approve", "submit", "execute",
    ]):
        return PermissionClass.CONTROLLED

    return PermissionClass.READ
