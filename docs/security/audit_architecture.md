# Security Audit Architecture

The Financial AI Operator includes a production-grade, append-only security auditing system built to track authentication, authorization, and administrative events deterministically.

## Architecture Principles

1. **Backend as Source of Truth**: The Next.js frontend (BFF) is completely excluded from audit logic. All security events are generated and persisted inside the FastAPI backend boundary.
2. **Append-Only Immutability**: The `SecurityEvent` model is protected via SQLAlchemy ORM event listeners (`before_update` and `before_delete`). Any attempt to modify or delete an existing audit log via the application layer will throw a fatal `ValueError`.
3. **Availability Resilience**: Failure to insert a security event does NOT crash the business transaction. If the database rejects an audit insert (e.g. string truncation), the error is caught, logged to standard error, and the primary transaction proceeds safely.
4. **Metadata Sanitization**: A recursive sanitization utility guarantees that passwords, password hashes, JWTs, and authorization headers NEVER enter the audit store, preventing accidental leakage.

## Event Vocabulary

All security events belong to a strict, centrally defined vocabulary (`SecurityEventType`):

- **Authentication**: `LOGIN_SUCCESS`, `LOGIN_FAILURE`, `LOGOUT`, `SESSION_REJECTED`, `TOKEN_REVOKED`
- **Identity / RBAC**: `PASSWORD_CHANGED`, `ADMIN_PASSWORD_RESET`, `ACCOUNT_ACTIVATED`, `ACCOUNT_DEACTIVATED`, `ROLE_CHANGED`
- **Authorization**: `AUTHORIZATION_DENIED`
- **Action Lifecycle**: `ACTION_REQUEST_CREATED`, `ACTION_REQUEST_APPROVED`, `ACTION_REQUEST_REJECTED`, `ACTION_REQUEST_CANCELLED`, `ACTION_EXECUTION_STARTED`, `ACTION_EXECUTION_SUCCEEDED`, `ACTION_EXECUTION_FAILED`

## RBAC Protection

The endpoint `/api/v1/admin/security-events` requires the explicit `VIEW_AUDIT_LOGS` permission.
This permission is exclusively granted to the `ADMIN` role. Operators and Finance Managers cannot view audit history.

## Performance Characteristics

To support high-volume audit writing without slowing down reads:
1. `created_at` is indexed descending.
2. `event_type` and `user_id` have explicit indexes.
3. Pagination is deterministically ordered by `(created_at DESC, id DESC)`.
