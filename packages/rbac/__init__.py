"""RBAC core: permission vocabulary, role matrix, and resolution helpers.

Authorization is ALWAYS derived from the authenticated user's roles in the
database — never from JWT claims, request bodies, headers, or frontend state.
"""

from packages.rbac.permissions import Permission, ALL_PERMISSIONS
from packages.rbac.matrix import (
    ROLE_PERMISSIONS,
    OPERATOR_PERMISSIONS,
    FINANCE_MANAGER_PERMISSIONS,
    ADMIN_PERMISSIONS,
    permissions_for_roles,
    permissions_for_user,
    user_has_permission,
)

__all__ = [
    "Permission",
    "ALL_PERMISSIONS",
    "ROLE_PERMISSIONS",
    "OPERATOR_PERMISSIONS",
    "FINANCE_MANAGER_PERMISSIONS",
    "ADMIN_PERMISSIONS",
    "permissions_for_roles",
    "permissions_for_user",
    "user_has_permission",
]