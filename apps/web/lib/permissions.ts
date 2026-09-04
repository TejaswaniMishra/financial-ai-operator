// Frontend authorization vocabulary — mirrors packages/rbac/permissions.py.
//
// IMPORTANT: frontend checks are UX only. Every protected backend endpoint
// independently enforces these permissions against the database. Hiding or
// disabling a control here never substitutes for backend authorization.

export const PERMISSIONS = {
  VIEW_DASHBOARD: "VIEW_DASHBOARD",
  VIEW_RECONCILIATION: "VIEW_RECONCILIATION",
  VIEW_DISCREPANCIES: "VIEW_DISCREPANCIES",
  VIEW_INVESTIGATIONS: "VIEW_INVESTIGATIONS",
  VIEW_ACTION_REQUESTS: "VIEW_ACTION_REQUESTS",
  VIEW_TRANSACTIONS: "VIEW_TRANSACTIONS",
  VIEW_SETTINGS: "VIEW_SETTINGS",
  VIEW_PERIODS: "VIEW_PERIODS",
  VIEW_REPORTS: "VIEW_REPORTS",
  RUN_INVESTIGATION: "RUN_INVESTIGATION",
  CREATE_PERIOD: "CREATE_PERIOD",
  EVALUATE_PERIOD_CLOSE: "EVALUATE_PERIOD_CLOSE",
  APPROVE_PERIOD_CLOSE: "APPROVE_PERIOD_CLOSE",
  CLOSE_PERIOD: "CLOSE_PERIOD",
  APPROVE_ACTION_REQUEST: "APPROVE_ACTION_REQUEST",
  REJECT_ACTION_REQUEST: "REJECT_ACTION_REQUEST",
  CANCEL_ACTION_REQUEST: "CANCEL_ACTION_REQUEST",
  EXECUTE_ACTION: "EXECUTE_ACTION",
  MANAGE_USERS: "MANAGE_USERS",
  MANAGE_ROLES: "MANAGE_ROLES",
  VIEW_AUDIT_LOGS: "VIEW_AUDIT_LOGS",
} as const;

export type PermissionCode = (typeof PERMISSIONS)[keyof typeof PERMISSIONS];

/**
 * True only when the authenticated user's backend-resolved permissions
 * include the given permission. `user` is the AuthProvider user object.
 */
export function hasPermission(
  user: { permissions?: string[] } | null | undefined,
  permission: PermissionCode | string
): boolean {
  return !!user && user.permissions?.includes(permission) === true;
}