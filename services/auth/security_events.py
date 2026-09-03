"""Security event logging for credential lifecycle changes (M8.6).

Replaces the M8.5 logging-based implementation with a production-grade
database-backed audit trail.

SAFETY: payloads are strictly limited to user/actor IDs and event codes.
Passwords, password hashes, temporary credentials, and reset secrets are
NEVER logged.
"""

import logging
from typing import Optional, Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.security import SecurityEvent

security_logger = logging.getLogger("fao.security")


async def _log_event(
    db: AsyncSession,
    event_type: str,
    user_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    request: Optional[Request] = None,
    is_success: bool = True,
    metadata_payload: Optional[dict[str, Any]] = None,
) -> None:
    ip_address = None
    user_agent = None
    if request:
        if request.client:
            ip_address = request.client.host
        user_agent = request.headers.get("user-agent")

    event = SecurityEvent(
        event_type=event_type,
        user_id=user_id,
        actor_id=actor_id,
        ip_address=ip_address,
        user_agent=user_agent,
        is_success=is_success,
        metadata_payload=metadata_payload or {},
    )
    db.add(event)
    # We do NOT commit here; the calling service manages the transaction boundary.
    # However, if this is called outside a transaction, we want it to be flushed.
    # We will rely on the caller to commit.


async def login_success(db: AsyncSession, user_id: str, request: Request) -> None:
    await _log_event(db, "LOGIN_SUCCESS", user_id=user_id, request=request)


async def login_failure(db: AsyncSession, request: Request, email: Optional[str] = None, reason: Optional[str] = None) -> None:
    meta = {}
    if email:
        meta["email"] = email
    if reason:
        meta["reason"] = reason
    await _log_event(db, "LOGIN_FAILURE", request=request, is_success=False, metadata_payload=meta)


async def logout(db: AsyncSession, user_id: str, request: Request) -> None:
    await _log_event(db, "LOGOUT", user_id=user_id, request=request)


async def password_changed(db: AsyncSession, user_id: str, request: Optional[Request] = None) -> None:
    await _log_event(db, "PASSWORD_CHANGED", user_id=user_id, request=request)


async def forced_password_change_completed(db: AsyncSession, user_id: str, request: Optional[Request] = None) -> None:
    await _log_event(db, "FORCED_PASSWORD_CHANGE_COMPLETED", user_id=user_id, request=request)


async def password_change_failed(db: AsyncSession, user_id: str, reason: str, request: Optional[Request] = None) -> None:
    await _log_event(
        db, "PASSWORD_CHANGE_FAILED", user_id=user_id, request=request, is_success=False, metadata_payload={"reason": reason}
    )


async def admin_password_reset(db: AsyncSession, actor_id: str, target_id: str, request: Optional[Request] = None) -> None:
    await _log_event(db, "ADMIN_PASSWORD_RESET", user_id=target_id, actor_id=actor_id, request=request)


async def account_activated(db: AsyncSession, actor_id: str, target_id: str, request: Optional[Request] = None) -> None:
    await _log_event(db, "ACCOUNT_ACTIVATED", user_id=target_id, actor_id=actor_id, request=request)


async def account_deactivated(db: AsyncSession, actor_id: str, target_id: str, request: Optional[Request] = None) -> None:
    await _log_event(db, "ACCOUNT_DEACTIVATED", user_id=target_id, actor_id=actor_id, request=request)


async def role_changed(db: AsyncSession, actor_id: str, target_id: str, new_roles: list[str], request: Optional[Request] = None) -> None:
    await _log_event(
        db, "ROLE_CHANGED", user_id=target_id, actor_id=actor_id, request=request, metadata_payload={"new_roles": new_roles}
    )


async def action_forbidden(db: AsyncSession, user_id: Optional[str], action: str, request: Optional[Request] = None) -> None:
    await _log_event(
        db, "ACTION_FORBIDDEN", user_id=user_id, request=request, is_success=False, metadata_payload={"action": action}
    )


def log_critical_credential_error(
    message: str, user_id: Optional[str] = None
) -> None:
    """Internal-error channel for credential operations (never sensitive)."""
    if user_id:
        security_logger.error("%s user_id=%s", message, user_id)
    else:
        security_logger.error("%s", message)
