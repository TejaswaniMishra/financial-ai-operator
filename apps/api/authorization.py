"""FastAPI authorization dependencies (backend-enforced RBAC).

Every protected endpoint must independently authenticate the user
(get_current_user) and verify the required permission against the user's
DATABASE roles. Client-supplied roles, headers, query parameters, and JWT
claims are never trusted for authorization.
"""

from typing import Callable

from fastapi import Depends, HTTPException, status

from apps.api.auth import get_current_user
from database.models.identity import RoleName, User
from packages.rbac.matrix import permissions_for_user, user_has_permission
from packages.rbac.permissions import Permission

FORBIDDEN_RESPONSE = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="You do not have permission to perform this action",
)


def require_permission(permission: Permission) -> Callable:
    """Build a dependency that requires the authenticated user to hold
    `permission` (resolved from their database roles).

    - No/invalid token        → 401 (via get_current_user)
    - Authenticated but denied → 403
    """

    async def dependency(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if not user_has_permission(current_user, permission):
            raise FORBIDDEN_RESPONSE
        return current_user

    return dependency


def require_role(role: RoleName) -> Callable:
    """Build a dependency that requires the authenticated user to hold the
    exact database role `role`. Prefer require_permission for capability
    checks; this exists for coarse-grained role gates.
    """

    async def dependency(
        current_user: User = Depends(get_current_user),
    ) -> User:
        role_names = {ur.role.name for ur in current_user.roles if ur.role is not None}
        if role not in role_names:
            raise FORBIDDEN_RESPONSE
        return current_user

    return dependency


def permissions_for_current_user(user: User):
    """Expose resolved permissions for a user (used by /auth/me)."""
    return permissions_for_user(user)