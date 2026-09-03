# M8.4 — Admin User & Role Management

## Admin endpoints

All routes live under `/api/v1/admin` and require authentication plus a
specific permission:

| Endpoint | Method | Permission |
| --- | --- | --- |
| `/admin/users` | GET | `MANAGE_USERS` |
| `/admin/users/{user_id}` | GET | `MANAGE_USERS` |
| `/admin/users/{user_id}/activate` | POST | `MANAGE_USERS` |
| `/admin/users/{user_id}/deactivate` | POST | `MANAGE_USERS` |
| `/admin/users/{user_id}/roles` | PUT | `MANAGE_ROLES` |

Status codes: `401` unauthenticated (missing/invalid/revoked/expired token,
inactive user), `403` authenticated without the permission, `404` unknown
user, `409` business-rule rejection (see safety invariants), `422` invalid
role payload.

No route is ever public; the router-level `get_current_user` plus per-route
`require_permission(...)` gates mirror every other protected router.

## Fixed role vocabulary

Exactly three roles exist and are validated server-side against
`RoleName`: `OPERATOR`, `FINANCE_MANAGER`, `ADMIN`. Role payloads use
pydantic `List[RoleName]`, so an unknown role string fails with 422. No
arbitrary/custom role can ever be created through the API, and the frontend
never supplies a role vocabulary of its own.

## User activation / deactivation

- `activate` / `deactivate` are **idempotent** — repeating either is a safe
  no-op that returns the current state.
- Deactivation is reversible and preserves the account, its credentials,
  role history, and audit trail. Users are never deleted in this milestone.
- A deactivated user's existing JWT immediately stops authorizing: the next
  protected request returns **401** because `get_current_user` checks
  `is_active` in the database on every request.

## Role assignment

`PUT /admin/users/{user_id}/roles` **replaces** the user's full role set
atomically (old assignments deleted, new assignments inserted in one
transaction). Duplicate input is normalized deterministically to the
canonical order `OPERATOR → FINANCE_MANAGER → ADMIN`. Existing sessions need
no refresh: because authorization is DB-backed, the next `/me` and every
subsequent protected request reflects the change immediately.

## Final-active-ADMIN safety invariant

The system can never be left without an active ADMIN:

- An admin cannot deactivate their **own** account (409).
- The final active ADMIN can never be **deactivated** (409).
- The final active ADMIN can never **lose the ADMIN role** (409) — e.g. a
  solo ADMIN attempting `{"roles": ["OPERATOR"]}` on their own account is
  rejected with no database mutation.

Both invariants live in `services/admin/user_management.py` and are covered
by DB-backed tests.

## DB-authoritative authorization

Permissions are resolved from the `user_roles`/`roles` tables on every
request. The backend never trusts:

- `role` / `roles` / `permissions` fields in request bodies,
- `X-Role`-style headers,
- JWT role/permission claims (JWTs carry identity/lifecycle claims only).

Escalation attempts via each of these channels are covered by tests and all
fail with 403.

## No password management in this milestone

Password reset/change is deliberately out of scope and belongs to a separate
security milestone. No admin endpoint accepts or returns password material,
and no admin endpoint can create users.

## No financial execution changes

Admin identity management does not touch action-request approval/rejection,
execution gates, the Policy Engine, or LLM/investigation behavior. M8.1–M8.3
behavior is preserved (the full backend suite stays green).

## BFF CSRF protection

All mutating admin calls (activate, deactivate, role PUT) go through the
Next.js BFF, which enforces the project-wide CSRF rule documented in
`m8_authentication_frontend.md`: `POST`/`PUT`/`PATCH`/`DELETE` requests must
carry a matching `Origin` (or `Referer`) header, or the BFF rejects them.
Browser requests include this automatically; non-browser clients and tests
must send `Origin: http://localhost:3000` (dev) explicitly. This protection
is security behavior and must not be weakened.

## Frontend behavior

- Navigation: the sidebar shows **Administration → User Management** only
  when the authenticated user's `/me` permissions include `MANAGE_USERS` or
  `MANAGE_ROLES`.
- `/admin` and `/admin/users/[id]`: permission-gated pages that show a clean
  permission-denied state when the user lacks access (the backend still
  enforces 403 independently), plus loading / error / empty / 404 states.
- Mutations (activate, deactivate, role changes) never optimistically show
  success — they wait for the backend response and then refetch the
  authoritative user data. Deactivation and ADMIN-granting show explicit
  confirmations.
- No localStorage/sessionStorage is used for identity or authorization
  state; AuthProvider remains the single identity source.