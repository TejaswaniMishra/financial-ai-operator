# Audit Log Retention Policy

## Core Principle

The Financial AI Operator maintains an **append-only, non-cascading** security audit log.

Audit records (`SecurityEvent`) are legally and operationally significant. Under no circumstances should the application automatically delete audit logs as part of normal operations.

## Non-Cascading User Deletion

If a user account (`User`) is deleted from the system, **the associated audit records are preserved**. The `user_id` and `actor_id` foreign keys in the `security_events` table are configured as `ON DELETE SET NULL` at the database level.

This ensures that the destruction of a user record does not silently wipe the historical record of their actions.

## Manual Retention & Archiving

Because the `security_events` table will grow indefinitely, database administrators should implement an out-of-band archiving process for records older than the organization's compliance window (e.g., 90 days, 1 year, or 7 years).

The application does NOT provide an API to delete or truncate audit logs. This must be performed by a DBA executing direct SQL (which bypasses the application-level ORM protection).

### Recommended Archival Process

1. Dump records older than the retention threshold to cold storage (e.g., AWS S3, Glacier) in a verifiable format (JSON/CSV).
2. Use raw SQL to delete the exported rows from the operational database.
3. Verify that the application continues to write new logs unaffected.
