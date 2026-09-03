# M8.5 — Secure Password Management & Account Security

## Password lifecycle overview

Every credential in the system is an **Argon2id hash** stored in the
`user_credentials` row of the owning `users` row. Plaintext passwords never
touch the database, logs, exceptions, or API responses (the single designed
exception: an admin reset returns the generated one-time temporary password
exactly once, shown only to the administrator).

Three lifecycle paths exist, all funneled through one service
(`services/auth/password_management.py`):

1. **Self-service change** — the authenticated user proves their current
   password and sets a new one.
2. **Admin-initiated reset** — an admin with `MANAGE_USERS` generates a
   server-side temporary credential for another user.
3. **Forced password change** — the completion step of an admin reset: the
   target authenticates with the temporary credential and must choose a new
   password before any protected functionality works.

## Argon2id

`packages/utils/crypto.py` hashes with the `argon2-cffi` `PasswordHasher`
defaults, i.e. **Argon2id** with current RFC-recommended parameters. There is
no reversible encryption, no MD5, and no SHA-only storage. Hashing never
logs its input.

## Password policy

One centralized policy (`packages/utils/password_policy.py`,
12-character minimum) is enforced by `validate_password()` on **every**
path — signup, self-service change, admin-reset temporary generation, and
the forced change — so no path can drift from the policy. The temporary
credential generator (`secrets.token_urlsafe(12)` → 16 URL-safe chars) is
deliberately above the minimum.

## Endpoints

| Endpoint | Method | Auth / permission |
| --- | --- | --- |
| `/api/v1/auth/change-password` | POST | authenticated user (self only) |
| `/api/v1/admin/users/{user_id}/password-reset` | POST | `MANAGE_USERS` |

`change-password` takes `{current_password, new_password}`. The target is
always the authenticated user — the schema accepts **no** `user_id`, so a
request can never change another account's password.

`password-reset` takes no body. The service generates the temporary
credential server-side, persists only its Argon2id hash, and returns it in
the response exactly once (`temporary_password`, `must_change_password:
true`). It is never logged, stored, or returned again.

Error behavior:

- `401` — missing/invalid/expired/revoked token, or inactive user.
- `400` — incorrect current password, new password equal to the current
  one, or an admin attempting to reset their own account (use the
  self-service endpoint instead).
- `404` — reset target does not exist.
- `422` — new password violates the centralized policy.
- `403` — authenticated user without `MANAGE_USERS` on the reset route.
- `500` (safe detail only) — unexpected credential-layer failure.

No response on any path exposes `password_hash`, credential rows, Argon2
parameters, reset secrets beyond the designed one-time case, JWT/jti data,
or token-revocation internals.

## Session/token invalidation — the credential version

A single password change/reset must kill **all** of the user's existing
sessions, not just the current one. Per-JTI revocation alone cannot do that,
so `users` carries a `credential_version` (DB default 1, `server_default`
keeps pre-existing rows valid) and the JWT embeds it as the **`cver`**
claim.

- Issuance reads the current DB version at login.
- `get_current_user` compares the token's `cver` to the DB value on every
  request; a mismatch is treated exactly like an invalid token → **401**.
- A successful password change or admin reset **increments** the version in
  the same transaction that replaces the hash. Every previously issued JWT
  for that user becomes invalid immediately.

The JWT still carries **identity/lifecycle claims only** — no roles, no
permissions. Authorization continues to resolve from the database. Existing
jti revocation and logout behavior are unchanged and continue to return 401
for revoked/expired tokens.

## Forced password change

`users.must_change_password` is a backend-controlled boolean:

- Set to `True` by an admin password reset.
- The target **may authenticate** with the temporary credential.
- While the flag is set, the auth dependency denies protected endpoints
  (403-style gate; `/me` and the change-password endpoint remain reachable
  so the user can complete the flow).
- `/me` exposes the safe boolean `must_change_password` so the frontend can
  route the user to `/password-change`; nothing sensitive is exposed.
- A successful change clears the flag (and bumps the version, killing the
  temporary-credential session) — the user signs in again normally.
- The temporary credential is single-use in effect: after the change the
  version no longer matches and the temp password fails verification.

The frontend gate is **UX routing only**. The backend independently refuses
protected functionality until the flag is cleared — a client cannot bypass
it by editing React state or navigating directly.

## BFF flow & CSRF

Browser → Next.js BFF (`/api/auth/change-password` is served via the
catch-all `/api/v1/...` proxy, and `/api/auth/me` supplies the forced flag)
→ FastAPI. The JWT lives only in the HttpOnly `fao_session` cookie; browser
JavaScript never sees it. Mutating requests continue to require the existing
**Origin** header enforced by the BFF CSRF layer — automated tests and
scripts must send `Origin`, and CSRF must not be weakened for convenience.
No credentials or tokens are stored in `localStorage`/`sessionStorage`, and
passwords never appear in URLs.

## Authorization boundaries

- `MANAGE_USERS` (DB-resolved from the actor's roles) is the only thing that
  authorizes an admin password reset. Forged body roles, `X-Role` headers,
  or fabricated JWT role claims change nothing — authorization comes from
  the authenticated database user.
- OPERATOR and FINANCE_MANAGER receive `403` on the reset route regardless
  of what they send.
- The last-active-ADMIN invariant from M8.4 is untouched: resetting another
  admin's password does not remove their ADMIN role, and a reset never
  deactivates an account, so the invariant cannot be violated through this
  route. Self-reset is explicitly disallowed (use the self-service path).

## Audit / security events

The project has no global audit table (only per-entity models such as
`ActionRequestAudit`), so this milestone emits credential events through a
dedicated `fao.security` logger (`services/auth/security_events.py`):

- `PASSWORD_CHANGED`
- `ADMIN_PASSWORD_RESET`
- `PASSWORD_CHANGE_FAILED` (reason only: wrong current password)
- `FORCED_PASSWORD_CHANGE_COMPLETED`

Payloads are strictly IDs, actor IDs, and event codes. Passwords, hashes,
temporary credentials, and reset secrets are **never** logged.

## Threat model

| Threat | Mitigation |
| --- | --- |
| Reused/leaked password | Argon2id hashing; version bump kills old sessions |
| Stolen JWT survives password change | `credential_version` in `cver` claim checked per request |
| Stolen JWT carries fake roles | JWT has no role claims; DB is authoritative |
| Operator escalates via body/header | Auth from DB only; body role fields ignored |
| Forced-change bypass | Backend denies protected endpoints until flag clears |
| Admin resets their own account | Rejected (`SelfResetNotAllowedError`, 400) |
| Reset target reuses temp forever | Single-use; cleared on change, version-bumped |
| Hash/token leakage in responses | Dedicated schemas; whitelisted `/me` BFF fields |

## Known limitations

- **No email delivery.** There is no mail infrastructure in the repository;
  an admin reset hands the temporary credential to the administrator
  directly (shown once, must be delivered out-of-band).
- **No self-service "forgot password".** Account recovery without an admin
  is out of scope and should be its own security milestone.
- **No password history/reuse policy** beyond "must differ from the current
  password."
- **Argon2 parameters** are library defaults; tuning (cost factors, rehash
  on login) is a future hardening milestone.
- **No global audit table** — events use the `fao.security` logger until a
  proper audit subsystem exists.
- **No financial execution changes** — this milestone only touches the
  credential lifecycle; RBAC and the policy-gated execution chain are
  unchanged.
