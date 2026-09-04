# M8.2.6 — Frontend Authentication Architecture

## Overview

M8.2.6 adds a complete, secure authentication layer to the Financial AI Operator frontend.
The implementation uses a **Backend-for-Frontend (BFF)** pattern to avoid exposing JWTs to
browser JavaScript while remaining fully compatible with the existing FastAPI Bearer-token backend.

---

## Architecture

```
Browser                         Next.js Server                        FastAPI Backend
  │                                   │                                       │
  ├── POST /api/auth/login ──────────►│ Verify with FastAPI                   │
  │   { email, password }             ├── POST /api/v1/auth/login ───────────►│
  │                                   │◄── { access_token } ──────────────────│
  │◄── 200, Set-Cookie:               │
  │    fao_session=<jwt> (HttpOnly)   │
  │                                   │
  ├── GET /api/v1/investigations ────►│ Read cookie, inject Authorization
  │                                   ├── GET /api/v1/investigations ─────────►│
  │◄── 200 [...]  ────────────────────│◄── 200 [...] ─────────────────────────│
  │                                   │
  ├── POST /api/auth/logout ─────────►│ Revoke token at FastAPI
  │                                   ├── POST /api/v1/auth/logout ───────────►│
  │◄── 200, clear fao_session cookie ─│◄── 200 ────────────────────────────────│
```

The browser **never** sees or touches the JWT.

---

## Token / Session Storage Strategy

| Storage        | Used? | Reason                                        |
|----------------|-------|-----------------------------------------------|
| `localStorage` | ❌    | Accessible to JavaScript — XSS vector         |
| `sessionStorage` | ❌  | Accessible to JavaScript — XSS vector         |
| Memory (React state) | ❌ | JWT never enters React state              |
| HttpOnly cookie (`fao_session`) | ✅ | Inaccessible to JS, SameSite Lax |

Cookie attributes:
- `httpOnly: true` — no JS access
- `secure: true` (production only)
- `sameSite: "lax"` — CSRF protection for cross-site navigation
- `path: "/"` — scoped to entire application
- `maxAge`: aligned with the backend JWT lifetime (read from the token's `exp` claim; `ACCESS_TOKEN_EXPIRE_MINUTES` backend default is 20 minutes)

---

## CSRF Protection

Because cookie-based auth is used for state-changing requests, CSRF protection is implemented:

1. **SameSite=Lax** on the session cookie (primary protection).
2. **Origin/Referer validation** in `proxyAuthenticatedRequest` and all auth route handlers
   for POST/PUT/PATCH/DELETE methods. Requests with a mismatched or missing Origin/Referer
   are rejected with HTTP 403.
3. The catch-all `/api/v1/[...path]` proxy only accepts requests from the same Next.js origin.

---

## Key Files

| File | Purpose |
|------|---------|
| `apps/web/lib/server/api-proxy.ts` | Core BFF helper: `proxyAuthenticatedRequest` |
| `apps/web/lib/server/redirect.ts` | Open-redirect prevention: `validateNextParam` |
| `apps/web/app/api/auth/login/route.ts` | BFF login: calls FastAPI, sets HttpOnly cookie |
| `apps/web/app/api/auth/signup/route.ts` | BFF signup: sanitises payload, no role assignment |
| `apps/web/app/api/auth/logout/route.ts` | BFF logout: revokes token, clears cookie |
| `apps/web/app/api/auth/me/route.ts` | BFF /me: returns safe `CurrentUser` subset |
| `apps/web/app/api/v1/[...path]/route.ts` | Catch-all proxy: injects Auth from cookie |
| `apps/web/middleware.ts` | Edge: fast cookie-presence check → redirect |
| `apps/web/components/providers/auth-provider.tsx` | React context: `useAuth` hook |
| `apps/web/lib/api.ts` | Client API: `login`, `logout`, `signup`, `fetchCurrentUser` |
| `apps/web/app/login/page.tsx` | Login page |
| `apps/web/app/signup/page.tsx` | Signup page |

---

## Authentication Flow

### Login
1. User submits email + password on `/login`.
2. Browser POSTs to `/api/auth/login` (Next.js BFF route).
3. BFF validates Origin/Referer (CSRF check).
4. BFF forwards credentials to `POST /api/v1/auth/login` on FastAPI.
5. FastAPI returns `{ access_token, token_type }`.
6. BFF sets `fao_session=<token>` as an HttpOnly cookie.
7. BFF returns `{ ok: true }` — **the token never reaches the browser**.
8. `AuthProvider` calls `/api/auth/me` to load `CurrentUser`.
9. User is redirected to the intended destination (validated to be internal-only).

### Signup
1. User submits display name, email, password, confirm password on `/signup`.
2. Browser POSTs to `/api/auth/signup`.
3. BFF strips any `role`/`is_active` fields from the payload.
4. BFF forwards to `POST /api/v1/auth/signup` on FastAPI.
5. Backend creates account, assigns default role (frontend has no say).
6. BFF returns `{ ok: true }` — **no auto-login**.
7. User is redirected to `/login`.

### Logout
1. User clicks "Sign out".
2. `AuthProvider.logout()` calls `/api/auth/logout`.
3. BFF reads the cookie, calls `POST /api/v1/auth/logout` on FastAPI (token revoked in DB).
4. Regardless of backend result, BFF clears the `fao_session` cookie.
5. `AuthProvider` clears React user state.
6. User is redirected to `/login`.

---

## Protected Routes

Edge Middleware (`middleware.ts`) performs a **fast cookie-presence check** before
any protected page renders. If `fao_session` is absent, the user is redirected to
`/login?next=<intended-path>`.

Protected paths:
- `/` (dashboard)
- `/reconciliation`
- `/discrepancies`
- `/investigations` and all sub-routes
- `/settings`
- `/action-requests` and all sub-routes

This is a **first-line-of-defence** only. The FastAPI backend validates the token on every
authenticated API call. An expired or revoked cookie triggers a 401 from FastAPI, which is
handled by the 401 handling strategy below.

### Open Redirect Prevention

The `next` query parameter is validated by `validateNextParam` (in `lib/server/redirect.ts`):
- Must start with `/`
- Must not start with `//` (protocol-relative URLs)
- Must not contain a protocol (`http:`, `https:`, etc.)
- Must not include auth paths (`/login`, `/signup`)
- Only printable ASCII characters allowed

---

## 401 / Session Expiry Handling

When `fetchAuthenticated` (in `api.ts`) receives a 401 from the BFF proxy:

1. It dispatches a `CustomEvent("fao:unauthorized")` on `window`.
2. `AuthProvider` listens for this event.
3. React user state is cleared.
4. User is redirected to `/login?next=<current-path>`.

**Loop prevention**: Auth routes (`/api/auth/*`) never trigger this event.
Edge middleware never redirects `/login` or `/signup`.

---

## CurrentUser Type

```typescript
interface CurrentUser {
  id: string;
  email: string;
  display_name: string | null;
  is_active: boolean;
}
```

This type is explicitly constructed by the `/api/auth/me` BFF route — **only these four
fields** are forwarded from the FastAPI response. No roles, no credential data, no internals.

---

## Security Considerations

| Concern | Mitigation |
|---------|-----------|
| JWT in localStorage | ❌ Never stored — HttpOnly cookie only |
| JWT in React state | ❌ Never placed in state |
| JWT in URL params | ❌ Never used |
| JWT in console logs | ❌ No token logging in BFF routes |
| Password logging | ❌ Never logged |
| Open redirect | ✅ `validateNextParam` rejects external URLs |
| CSRF | ✅ SameSite=Lax + Origin/Referer validation |
| XSS via display name | ✅ React escapes user-controlled strings by default |
| Expired/revoked token | ✅ FastAPI returns 401 → `fao:unauthorized` event → logout |
| Role spoofing on signup | ✅ BFF strips role/is_active fields before forwarding |
| Redirect loop | ✅ Auth paths excluded from 401 redirect + middleware exclusion |

---

## What Is NOT Implemented (By Design)

| Feature | Status |
|---------|--------|
| RBAC / role-based UI | ❌ Not implemented — M8.3+ |
| Refresh tokens | ❌ Not implemented — M8.2.7+ |
| Password reset | ❌ Not implemented |
| Email verification | ❌ Not implemented |
| MFA / 2FA | ❌ Not implemented |
| Profile editing | ❌ Not implemented |
| Social login | ❌ Not implemented |
| Admin user management UI | ❌ Not implemented |
| Frontend role assignment | ❌ Intentionally prevented |

---

## Relationship to Backend M8.2.1–M8.2.5

| Backend Milestone | Frontend Integration |
|-------------------|---------------------|
| M8.2.1 — Credential Foundation | Password hash never sent to frontend |
| M8.2.2 — Secure Signup | `/api/auth/signup` BFF proxies to `/api/v1/auth/signup` |
| M8.2.3 — JWT Login | `/api/auth/login` BFF proxies to `/api/v1/auth/login`, stores token in cookie |
| M8.2.4 — Protected API + /me | `/api/auth/me` BFF proxies to `/api/v1/auth/me` |
| M8.2.5 — Token Revocation | `/api/auth/logout` BFF proxies to `/api/v1/auth/logout` (token revoked server-side) |

**Authentication is not authorisation.** The frontend does not enforce business permissions.
Financial actions remain gated by backend policy evaluation and action execution logic.
