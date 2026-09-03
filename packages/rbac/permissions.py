"""Centralized permission vocabulary for the platform.

Keep this intentionally small and tied to existing capabilities.
Adding a permission here does NOT grant anything — it must also be wired
into the role matrix and the protected endpoints.
"""

import enum


class Permission(str, enum.Enum):
    """Every capability the backend can enforce. Values are stable API codes."""

    # Read-only views
    VIEW_DASHBOARD = "VIEW_DASHBOARD"
    VIEW_RECONCILIATION = "VIEW_RECONCILIATION"
    VIEW_DISCREPANCIES = "VIEW_DISCREPANCIES"
    VIEW_INVESTIGATIONS = "VIEW_INVESTIGATIONS"
    VIEW_ACTION_REQUESTS = "VIEW_ACTION_REQUESTS"
    VIEW_TRANSACTIONS = "VIEW_TRANSACTIONS"
    VIEW_SETTINGS = "VIEW_SETTINGS"

    # Investigation workflow
    RUN_INVESTIGATION = "RUN_INVESTIGATION"

    # Financial decision actions (never available to OPERATOR)
    APPROVE_ACTION_REQUEST = "APPROVE_ACTION_REQUEST"
    REJECT_ACTION_REQUEST = "REJECT_ACTION_REQUEST"
    CANCEL_ACTION_REQUEST = "CANCEL_ACTION_REQUEST"
    EXECUTE_ACTION = "EXECUTE_ACTION"

    # Administrative capabilities
    MANAGE_USERS = "MANAGE_USERS"
    MANAGE_ROLES = "MANAGE_ROLES"
    VIEW_AUDIT_LOGS = "VIEW_AUDIT_LOGS"


ALL_PERMISSIONS = frozenset(Permission)