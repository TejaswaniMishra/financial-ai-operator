"""Security event logging for credential lifecycle changes (M8.5).

The project has no global audit table yet (only per-entity audit models such
as ActionRequestAudit), so password-security events are emitted through a
dedicated `fao.security` logger using the standard library. This gives the
event vocabulary (PASSWORD_CHANGED, ADMIN_PASSWORD_RESET, ...) without
building an unrelated audit subsystem.

SAFETY: payloads are strictly limited to user/actor IDs and event codes.
Passwords, password hashes, temporary credentials, and reset secrets are
NEVER logged.
"""

import logging
from typing import Optional

security_logger = logging.getLogger("fao.security")


def password_changed(user_id: str) -> None:
    security_logger.info(
        "PASSWORD_CHANGED user_id=%s", user_id
    )


def forced_password_change_completed(user_id: str) -> None:
    security_logger.info(
        "FORCED_PASSWORD_CHANGE_COMPLETED user_id=%s", user_id
    )


def password_change_failed(user_id: str, reason: str) -> None:
    security_logger.info(
        "PASSWORD_CHANGE_FAILED user_id=%s reason=%s", user_id, reason
    )


def admin_password_reset(actor_id: str, target_id: str) -> None:
    security_logger.info(
        "ADMIN_PASSWORD_RESET actor_id=%s target_id=%s", actor_id, target_id
    )


def log_critical_credential_error(
    message: str, user_id: Optional[str] = None
) -> None:
    """Internal-error channel for credential operations (never sensitive)."""
    if user_id:
        security_logger.error("%s user_id=%s", message, user_id)
    else:
        security_logger.error("%s", message)
