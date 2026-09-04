"""Security event logging for credential lifecycle changes (M8.6).

Replaces the M8.5 logging-based implementation with a production-grade
database-backed audit trail.

SAFETY: payloads are strictly limited to user/actor IDs and event codes.
Passwords, password hashes, temporary credentials, and reset secrets are
NEVER logged.
"""

import logging
import json
from typing import Optional, Any
from sqlalchemy.exc import SQLAlchemyError
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.security import SecurityEvent, SecurityEventType

security_logger = logging.getLogger("fao.security")

# Strongly forbidden keys in metadata
FORBIDDEN_METADATA_KEYS = {
    "password", "password_hash", "token", "jwt", "authorization", 
    "secret", "api_key", "cookie", "session", "reasoning", 
    "chain_of_thought", "raw_llm_response", "context_snapshot"
}

def sanitize_metadata(payload: Optional[dict[str, Any]]) -> dict[str, Any]:
    """
    Ensure no sensitive data ever enters the security audit log.
    Rejects any keys containing forbidden substrings.
    """
    if not payload:
        return {}
    
    safe_payload = {}
    for k, v in payload.items():
        k_lower = k.lower()
        if any(forbidden in k_lower for forbidden in FORBIDDEN_METADATA_KEYS):
            security_logger.warning(f"Blocked attempt to log sensitive metadata key: {k}")
            continue
        
        # Recursively sanitize dicts
        if isinstance(v, dict):
            safe_payload[k] = sanitize_metadata(v)
        else:
            # We want to enforce simple serialization
            try:
                # Test json serializability
                json.dumps(v)
                safe_payload[k] = v
            except (TypeError, ValueError):
                safe_payload[k] = str(v)
    return safe_payload


async def _log_event(
    db: AsyncSession,
    event_type: SecurityEventType,
    user_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    request: Optional[Request] = None,
    is_success: bool = True,
    metadata_payload: Optional[dict[str, Any]] = None,
) -> None:
    """
    Persist a security event.
    Must never break the primary business operation if insertion fails.
    """
    try:
        ip_address = None
        user_agent = None
        if request:
            if request.client:
                ip_address = request.client.host
            user_agent = request.headers.get("user-agent")

        safe_metadata = sanitize_metadata(metadata_payload)

        event = SecurityEvent(
            event_type=event_type.value,
            user_id=user_id,
            actor_id=actor_id,
            ip_address=ip_address,
            user_agent=user_agent,
            is_success=is_success,
            metadata_payload=safe_metadata,
        )
        db.add(event)
        # We don't commit here. The caller's transaction handles it.
        # However, to test DB insert failures safely without rolling back the whole
        # transaction unnecessarily, we'd need nested transactions (savepoints) if we
        # wanted to flush and catch immediately. We'll simply let standard session 
        # semantics apply. If it fails on commit, the global error handler logs it.
    except Exception as e:
        security_logger.error("Failed to construct/enqueue security event: %s", str(e))


async def login_success(db: AsyncSession, user_id: str, request: Request) -> None:
    await _log_event(db, SecurityEventType.LOGIN_SUCCESS, user_id=user_id, request=request)


async def login_failure(db: AsyncSession, request: Request, email: Optional[str] = None, reason: Optional[str] = None) -> None:
    meta = {}
    if email:
        meta["email"] = email
    if reason:
        meta["reason"] = reason
    await _log_event(db, SecurityEventType.LOGIN_FAILURE, request=request, is_success=False, metadata_payload=meta)


async def logout(db: AsyncSession, user_id: str, request: Request) -> None:
    await _log_event(db, SecurityEventType.LOGOUT, user_id=user_id, request=request)


async def password_changed(db: AsyncSession, user_id: str, request: Optional[Request] = None) -> None:
    await _log_event(db, SecurityEventType.PASSWORD_CHANGED, user_id=user_id, request=request)


async def forced_password_change_completed(db: AsyncSession, user_id: str, request: Optional[Request] = None) -> None:
    await _log_event(db, SecurityEventType.FORCED_PASSWORD_CHANGE, user_id=user_id, request=request)


async def password_change_failed(db: AsyncSession, user_id: str, reason: str, request: Optional[Request] = None) -> None:
    await _log_event(
        db, SecurityEventType.PASSWORD_CHANGED, user_id=user_id, request=request, is_success=False, metadata_payload={"reason": reason}
    )


async def admin_password_reset(db: AsyncSession, actor_id: str, target_id: str, request: Optional[Request] = None) -> None:
    await _log_event(db, SecurityEventType.ADMIN_PASSWORD_RESET, user_id=target_id, actor_id=actor_id, request=request)


async def account_activated(db: AsyncSession, actor_id: str, target_id: str, request: Optional[Request] = None) -> None:
    await _log_event(db, SecurityEventType.ACCOUNT_ACTIVATED, user_id=target_id, actor_id=actor_id, request=request)


async def account_deactivated(db: AsyncSession, actor_id: str, target_id: str, request: Optional[Request] = None) -> None:
    await _log_event(db, SecurityEventType.ACCOUNT_DEACTIVATED, user_id=target_id, actor_id=actor_id, request=request)


async def role_changed(db: AsyncSession, actor_id: str, target_id: str, new_roles: list[str], request: Optional[Request] = None) -> None:
    await _log_event(
        db, SecurityEventType.USER_ROLE_CHANGED, user_id=target_id, actor_id=actor_id, request=request, metadata_payload={"new_roles": new_roles}
    )


async def action_forbidden(db: AsyncSession, user_id: Optional[str], action: str, request: Optional[Request] = None) -> None:
    await _log_event(
        db, SecurityEventType.AUTHORIZATION_DENIED, user_id=user_id, request=request, is_success=False, metadata_payload={"action": action}
    )

async def action_request_created(db: AsyncSession, user_id: str, request_id: str, request: Optional[Request] = None) -> None:
    await _log_event(db, SecurityEventType.ACTION_REQUEST_CREATED, user_id=user_id, actor_id=user_id, request=request, metadata_payload={"request_id": request_id})

async def action_request_approved(db: AsyncSession, actor_id: str, request_id: str, request: Optional[Request] = None) -> None:
    await _log_event(db, SecurityEventType.ACTION_REQUEST_APPROVED, actor_id=actor_id, request=request, metadata_payload={"request_id": request_id})

async def action_request_rejected(db: AsyncSession, actor_id: str, request_id: str, request: Optional[Request] = None) -> None:
    await _log_event(db, SecurityEventType.ACTION_REQUEST_REJECTED, actor_id=actor_id, request=request, metadata_payload={"request_id": request_id})

async def action_request_cancelled(db: AsyncSession, actor_id: str, request_id: str, request: Optional[Request] = None) -> None:
    await _log_event(db, SecurityEventType.ACTION_REQUEST_CANCELLED, actor_id=actor_id, request=request, metadata_payload={"request_id": request_id})

async def action_execution_started(db: AsyncSession, actor_id: str, execution_id: str, request: Optional[Request] = None) -> None:
    await _log_event(db, SecurityEventType.ACTION_EXECUTION_STARTED, actor_id=actor_id, request=request, metadata_payload={"execution_id": execution_id})

async def action_execution_succeeded(db: AsyncSession, actor_id: str, execution_id: str, request: Optional[Request] = None) -> None:
    await _log_event(db, SecurityEventType.ACTION_EXECUTION_SUCCEEDED, actor_id=actor_id, request=request, metadata_payload={"execution_id": execution_id})

async def action_execution_failed(db: AsyncSession, actor_id: str, execution_id: str, error_category: str, request: Optional[Request] = None) -> None:
    await _log_event(
        db, SecurityEventType.ACTION_EXECUTION_FAILED, actor_id=actor_id, request=request, is_success=False, metadata_payload={"execution_id": execution_id, "error_category": error_category}
    )

async def session_rejected(db: AsyncSession, user_id: Optional[str], reason: str, request: Optional[Request] = None) -> None:
    await _log_event(
        db, SecurityEventType.SESSION_REJECTED, user_id=user_id, request=request, is_success=False, metadata_payload={"reason": reason}
    )

async def token_revoked(db: AsyncSession, user_id: Optional[str], jti: str, request: Optional[Request] = None) -> None:
    await _log_event(
        db, SecurityEventType.TOKEN_REVOKED, user_id=user_id, request=request, metadata_payload={"jti": jti}
    )

def log_critical_credential_error(
    message: str, user_id: Optional[str] = None
) -> None:
    """Internal-error channel for credential operations (never sensitive)."""
    if user_id:
        security_logger.error("%s user_id=%s", message, user_id)
    else:
        security_logger.error("%s", message)


# ─── MFA events ───────────────────────────────────────────────────────────────
# Only event codes + user/actor IDs are recorded. TOTP secrets, recovery-code
# plaintext, and codes are NEVER logged.

async def mfa_enrollment_started(db: AsyncSession, user_id: str, request: Optional[Request] = None) -> None:
    await _log_event(db, SecurityEventType.MFA_ENROLLMENT_STARTED, user_id=user_id, request=request)

async def mfa_enabled(db: AsyncSession, user_id: str, request: Optional[Request] = None) -> None:
    await _log_event(db, SecurityEventType.MFA_ENABLED, user_id=user_id, request=request)

async def mfa_disabled(db: AsyncSession, user_id: str, request: Optional[Request] = None) -> None:
    await _log_event(db, SecurityEventType.MFA_DISABLED, user_id=user_id, request=request)

async def mfa_verification_success(db: AsyncSession, user_id: str, request: Optional[Request] = None) -> None:
    await _log_event(db, SecurityEventType.MFA_VERIFICATION_SUCCESS, user_id=user_id, request=request)

async def mfa_verification_failed(db: AsyncSession, user_id: str, reason: str = "invalid_code", request: Optional[Request] = None) -> None:
    await _log_event(
        db,
        SecurityEventType.MFA_VERIFICATION_FAILED,
        user_id=user_id,
        request=request,
        is_success=False,
        metadata_payload={"reason": reason},
    )

async def mfa_challenge_issued(db: AsyncSession, user_id: str, request: Optional[Request] = None) -> None:
    await _log_event(db, SecurityEventType.MFA_CHALLENGE_ISSUED, user_id=user_id, request=request)

async def recovery_code_used(db: AsyncSession, user_id: str, request: Optional[Request] = None) -> None:
    await _log_event(db, SecurityEventType.RECOVERY_CODE_USED, user_id=user_id, request=request)

async def recovery_codes_regenerated(db: AsyncSession, user_id: str, request: Optional[Request] = None) -> None:
    await _log_event(db, SecurityEventType.RECOVERY_CODES_REGENERATED, user_id=user_id, request=request)


async def ingestion_started(db: AsyncSession, user_id: str, run_id: str) -> None:
    """Audit that an ingestion run was created (no raw source content logged)."""
    await _log_event(
        db,
        SecurityEventType.INGESTION_STARTED,
        user_id=user_id,
        metadata_payload={"run_id": run_id},
    )


async def ingestion_completed(db: AsyncSession, user_id: str, run_id: str) -> None:
    """Audit that an ingestion run completed without failures."""
    await _log_event(
        db,
        SecurityEventType.INGESTION_COMPLETED,
        user_id=user_id,
        metadata_payload={"run_id": run_id},
    )


async def ingestion_failed(db: AsyncSession, user_id: str, run_id: str) -> None:
    """Audit that an ingestion run completed with failures or crashed."""
    await _log_event(
        db,
        SecurityEventType.INGESTION_FAILED,
        user_id=user_id,
        is_success=False,
        metadata_payload={"run_id": run_id},
    )
