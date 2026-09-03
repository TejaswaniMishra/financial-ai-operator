# M8.3 — RBAC & Backend-Enforced Authorization

## Authentication vs Authorization

- **Authentication** answers *"Who is this user?"* — JWT identity (subject `sub`, `jti`, expiry), validated and revoked server-side; the HttpOnly BFF session carries the token.
- **Authorization** answers *"What is this user allowed to do?"* — resolved **from the database** on every request from the user's `UserRole` rows.

The backend is authoritative for both. Frontend permission checks are UX only.

## Role model

| Role              | Meaning                                        |
| ----------------- | ---------------------------------------------- |
| `OPERATOR`        | Read/analyze: dashboards, reconciliation, discrepancies, investigations, action-request viewing |
| `FINANCE_MANAGER` | OPERATOR + approve / reject / cancel / execute action requests |
| `ADMIN`           | FINANCE_MANAGER + `MANAGE_USERS`, `MANAGE_ROLES` |

Roles are seeded rows in the `roles` table (`database/seed_data/generator.py`), assigned to users via `user_roles` (unique per `(user_id, role_id)`). Signup assigns `OPERATOR` only; nothing else is created at runtime.

## Permission vocabulary

`packages/rbac/permissions.py` — intentionally small, tied to existing capabilities:

- Views: `VIEW_DASHBOARD`, `VIEW_RECONCILIATION`, `VIEW_DISCREPANCIES`, `VIEW_INVESTIGATIONS`, `VIEW_ACTION_REQUESTS`, `VIEW_TRANSACTIONS`, `VIEW_SETTINGS`
- Investigation workflow: `RUN_INVESTIGATION`
- Financial decisions (never OPERATOR): `APPROVE_ACTION_REQUEST`, `REJECT_ACTION_REQUEST`, `CANCEL_ACTION_REQUEST`, `EXECUTE_ACTION`
- Administration: `MANAGE_USERS`, `MANAGE_ROLES`

## Role → permission matrix

`packages/rbac/matrix.py` — deterministic, hierarchical (each role inherits the previous):

- `OPERATOR`: the eight view permissions + `RUN_INVESTIGATION`
- `FINANCE_MANAGER`: all OPERATOR + the four financial-decision permissions
- `ADMIN`: all FINANCE_MANAGER + `MANAGE_USERS`, `MANAGE_ROLES`

Multi-role users receive the **union** of their roles' permissions (`permissions_for_roles`).

## Backend enforcement

`apps/api/authorization.py` provides FastAPI dependencies:

- `require_permission(Permission.X)` — authenticates (`get_current_user`, 401 on failure) then loads the user's DB roles and resolves permissions; raises **403** if denied.
- `require_role(RoleName.Y)` — coarse role gate (prefer permissions).

Every protected endpoint carries an explicit `Depends(require_permission(...))`; the router-level `Depends(get_current_user)` remains as the authentication boundary. `get_current_user` eagerly loads `UserRole → Role` so authorization reads the database state for the current request — a role removed from the DB is denied on the very next request.

## 401 vs 403

- **401 Unauthenticated** — missing/invalid/revoked/expired token, deleted user, or inactive user (`get_current_user`).
- **403 Forbidden** — authenticated but the user's DB roles do not grant the required permission.

The BFF passes both statuses through; the frontend redirects to `/login` only on 401, and stays authenticated showing a permission state on 403.

## Why roles are never trusted from the JWT

`create_access_token` emits identity/lifecycle claims only (`sub`, `iat`, `exp`, `iss`, `aud`, `jti`) — **no roles, no permissions**. A token signed with forged role claims is validated for signature/claims but its extra claims are ignored; `/auth/me` and every protected endpoint resolve roles from the database. Request bodies, query parameters, and client headers are likewise never consulted for authorization.

## Current-user contract

`GET /api/v1/auth/me` (via BFF `GET /api/auth/me`) returns `CurrentUserResponse`:

```json
{
  "id": "...",
  "email": "...",
  "display_name": "...",
  "is_active": true,
  "roles": ["OPERATOR"],
  "permissions": ["VIEW_DASHBOARD", "..."]
}
```

No credentials, password hashes, JWT internals, or authorization diagnostics. The BFF whitelists exactly these fields for the browser.

## Frontend authorization (UX only)

- `apps/web/lib/permissions.ts` mirrors the vocabulary (`PERMISSIONS`, `hasPermission`).
- The AuthProvider `user` object carries the authoritative `roles`/`permissions` from `/me`.
- The sidebar shows the real role names (never hardcoded/inferred); multiple roles render joined by ` · `.
- Action-request controls (approve/reject/cancel/execute) are shown or disabled per permission, with a "You do not have permission" state on 403.

None of this substitutes for backend checks — every protected endpoint enforces permissions independently.

## Financial action protection

The execution chain is unchanged and enforced at every layer:

```
Investigation → Policy Engine → ActionRequest → Approval → Execution Authorization → Preflight → ActionExecution
```

- OPERATOR cannot approve, reject, cancel, or execute — even by calling the API directly (403).
- FINANCE_MANAGER/ADMIN may approve/reject/cancel and execute **only through the existing gates**: the ActionExecutionService refuses any request not in `APPROVED` state, and approval never directly triggers financial execution.

## Tests

`tests/integration/test_rbac.py` — DB-backed (SQLite) coverage: OPERATOR view/run capabilities; OPERATOR 403 on approve/reject/execute; FINANCE_MANAGER approve/reject and execute-through-gates; FM denied admin permissions; ADMIN granted admin + inherits lower roles; 401 for unauthenticated and inactive users; fake-role body/header/JWT-claim escalation attempts all fail; multi-role union; immediate effect of role removal; deterministic matrix; financial safety gates.