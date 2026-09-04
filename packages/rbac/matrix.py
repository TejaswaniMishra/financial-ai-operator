"""Deterministic role → permission matrix.

The mapping is the single source of truth for what each database role is
allowed to do. Roles are hierarchical: FINANCE_MANAGER inherits every
OPERATOR permission, and ADMIN inherits every FINANCE_MANAGER permission.
"""

from typing import Iterable, Set

from database.models.identity import RoleName
from packages.rbac.permissions import Permission

OPERATOR_PERMISSIONS = frozenset({
    Permission.VIEW_DASHBOARD,
    Permission.VIEW_RECONCILIATION,
    Permission.VIEW_DISCREPANCIES,
    Permission.VIEW_INVESTIGATIONS,
    Permission.RUN_INVESTIGATION,
    Permission.VIEW_ACTION_REQUESTS,
    Permission.VIEW_TRANSACTIONS,
    Permission.VIEW_SETTINGS,
    Permission.VIEW_PERIODS,
    Permission.CREATE_PERIOD,
    Permission.EVALUATE_PERIOD_CLOSE,
    Permission.VIEW_REPORTS,
})

FINANCE_MANAGER_PERMISSIONS = OPERATOR_PERMISSIONS | frozenset({
    Permission.APPROVE_ACTION_REQUEST,
    Permission.REJECT_ACTION_REQUEST,
    Permission.CANCEL_ACTION_REQUEST,
    Permission.EXECUTE_ACTION,
    Permission.APPROVE_PERIOD_CLOSE,
    Permission.CLOSE_PERIOD,
})

ADMIN_PERMISSIONS = FINANCE_MANAGER_PERMISSIONS | frozenset({
    Permission.MANAGE_USERS,
    Permission.MANAGE_ROLES,
    Permission.VIEW_AUDIT_LOGS,
})

ROLE_PERMISSIONS: dict[RoleName, frozenset[Permission]] = {
    RoleName.OPERATOR: OPERATOR_PERMISSIONS,
    RoleName.FINANCE_MANAGER: FINANCE_MANAGER_PERMISSIONS,
    RoleName.ADMIN: ADMIN_PERMISSIONS,
}


def permissions_for_roles(role_names: Iterable[RoleName]) -> Set[Permission]:
    """Resolve the union of permissions for a set of roles (deterministic)."""
    result: Set[Permission] = set()
    for name in role_names:
        result |= set(ROLE_PERMISSIONS.get(name, frozenset()))
    return result


def permissions_for_user(user) -> Set[Permission]:
    """Resolve the union of permissions for a DB-backed user object.

    Roles are read from the user's loaded UserRole relationships, which
    originate from the database — never from client input or tokens.
    """
    role_names = [ur.role.name for ur in user.roles if ur.role is not None]
    return permissions_for_roles(role_names)


def user_has_permission(user, permission: Permission) -> bool:
    """True only if the user's database roles grant the given permission."""
    return permission in permissions_for_user(user)