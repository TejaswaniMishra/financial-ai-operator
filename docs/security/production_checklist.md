# Production Security Hardening Checklist

When deploying the Financial AI Operator to a production environment, ensure the following observability and security mechanisms are active and validated.

## 1. Audit Logging Validation

- [ ] Verify that `SecurityEvent` ORM protections (append-only enforcement) are active.
- [ ] Confirm that `is_success` is properly capturing authentication failures and execution failures.
- [ ] Validate that metadata sanitization is active and recursive. Inject a mock payload with `"password"` and `"Authorization"` keys and verify they are scrubbed before persistence.

## 2. API Hardening

- [ ] Ensure `/api/v1/admin/security-events` requires `VIEW_AUDIT_LOGS` explicitly.
- [ ] Confirm that pagination (`limit` and `offset`) limits max records returned per request to prevent memory exhaustion attacks.
- [ ] Validate that the frontend Security Console securely displays JSON metadata without XSS vulnerabilities.

## 3. Database Layer

- [ ] Confirm the database schema applies `ON DELETE SET NULL` to user references in the `security_events` table.
- [ ] Ensure an index exists on `(created_at DESC)` and `event_type` in the database to guarantee performant filtering.

## 4. Resilience

- [ ] Introduce intentional database lock/timeout during a mock authentication event to ensure that the primary transaction (the login failure itself) survives the audit insertion failure.
- [ ] Verify error logs explicitly capture "Failed to log security event" safely.
