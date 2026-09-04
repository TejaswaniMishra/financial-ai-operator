from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete

from apps.api.auth import get_current_user
from apps.api.dependencies import get_db_session
from apps.api.routes.auth import _to_current_user_response
from database.models.identity import User, UserCredential
from database.models.mfa import MfaRecoveryCode
from packages.schemas.auth import TokenResponse
from packages.schemas.mfa import (
    LoginResultResponse,
    MfaDisableRequest,
    MfaRegenerateRequest,
    MfaSetupResponse,
    MfaVerifyRequest,
    MfaVerifySetupRequest,
    RecoveryCodesResponse,
)
from packages.utils.crypto import verify_password
from packages.utils.jwt import (
    MFA_CHALLENGE_SCOPE,
    create_access_token,
    decode_access_token,
    JWTError,
)
from services.auth import security_events
from services.auth.token_revocation import is_token_revoked, revoke_token
from services.mfa import service as mfa_service

router = APIRouter(
    prefix="/auth/mfa",
    tags=["MFA"],
)


def _credentials_exception(detail: str = "Invalid MFA verification") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def _load_credential(db: AsyncSession, user_id: str) -> UserCredential:
    stmt = select(UserCredential).where(UserCredential.user_id == user_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def _persist_recovery_codes(
    db: AsyncSession, user_id: str
) -> list[str]:
    """Replace the user's stored (hashed) recovery codes; returns plaintext once."""
    await db.execute(
        delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user_id)
    )
    plain = mfa_service.generate_recovery_codes()
    for code in plain:
        db.add(
            MfaRecoveryCode(
                user_id=user_id,
                code_hash=mfa_service.hash_recovery_code(code),
            )
        )
    return plain


async def _consume_recovery_code(db: AsyncSession, user_id: str, code: str) -> bool:
    """Single-use consumption of a recovery code. Returns True if consumed."""
    code_hash = mfa_service.hash_recovery_code(code)
    stmt = select(MfaRecoveryCode).where(
        MfaRecoveryCode.user_id == user_id,
        MfaRecoveryCode.code_hash == code_hash,
        MfaRecoveryCode.used.is_(False),
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        return False
    row.used = True
    row.used_at = datetime.now(timezone.utc).replace(tzinfo=None)
    return True


async def _verify_second_factor(
    db: AsyncSession, user: User, code: str
) -> tuple[bool, str]:
    """Returns (ok, method) where method is 'totp' | 'recovery' | ''."""
    secret = mfa_service.decrypt_secret(user.mfa_secret_encrypted) if user.mfa_secret_encrypted else None
    if secret and mfa_service.verify_totp(secret, code):
        return True, "totp"
    if await _consume_recovery_code(db, user.id, code):
        return True, "recovery"
    return False, ""


@router.post(
    "/setup",
    response_model=MfaSetupResponse,
    summary="Begin TOTP enrollment (returns the one-time secret)",
)
async def mfa_setup(
    req: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    if current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="MFA is already enabled for this account.",
        )
    secret = mfa_service.generate_totp_secret()
    current_user.mfa_secret_encrypted = mfa_service.encrypt_secret(secret)
    current_user.mfa_enabled = False
    await security_events.mfa_enrollment_started(db, current_user.id, req)
    await db.commit()
    return MfaSetupResponse(
        secret=secret,
        otpauth_url=mfa_service.totp_uri(secret, current_user.email),
    )


@router.post(
    "/verify-setup",
    response_model=RecoveryCodesResponse,
    summary="Confirm enrollment with a live TOTP code; enables MFA",
)
async def mfa_verify_setup(
    payload: MfaVerifySetupRequest,
    req: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    if current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="MFA is already enabled for this account.",
        )
    if not current_user.mfa_secret_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending MFA enrollment. Call /auth/mfa/setup first.",
        )
    secret = mfa_service.decrypt_secret(current_user.mfa_secret_encrypted) or ""
    if not mfa_service.verify_totp(secret, payload.code):
        await security_events.mfa_verification_failed(
            db, current_user.id, reason="invalid_enrollment_code", request=req
        )
        await db.commit()
        raise _credentials_exception("Invalid authenticator code.")
    current_user.mfa_enabled = True
    codes = await _persist_recovery_codes(db, current_user.id)
    await security_events.mfa_enabled(db, current_user.id, req)
    await db.commit()
    return RecoveryCodesResponse(codes=codes)


@router.post(
    "/verify",
    response_model=TokenResponse,
    summary="Complete login with TOTP/recovery code, returning the session token",
)
async def mfa_verify(
    payload: MfaVerifyRequest,
    req: Request,
    db: AsyncSession = Depends(get_db_session),
):
    # Only challenge-scoped tokens may be exchanged here.
    try:
        claims = decode_access_token(payload.mfa_token)
    except JWTError:
        raise _credentials_exception("Invalid or expired MFA challenge.")
    if claims.get("scope") != MFA_CHALLENGE_SCOPE:
        raise _credentials_exception("Invalid MFA challenge.")

    user_id = claims.get("sub")
    jti = claims.get("jti")
    if not user_id or not jti:
        raise _credentials_exception("Invalid MFA challenge.")
    if await is_token_revoked(db, jti):
        raise _credentials_exception("MFA challenge has already been used.")

    stmt = select(User).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if user is None or not user.is_active:
        raise _credentials_exception("Account is not available.")
    if not user.mfa_enabled:
        raise _credentials_exception("MFA is not enabled for this account.")
    if (claims.get("cver") or None) != user.credential_version:
        raise _credentials_exception("Credentials have changed. Please log in again.")

    ok, method = await _verify_second_factor(db, user, payload.code)
    if not ok:
        await security_events.mfa_verification_failed(
            db, user.id, reason="invalid_code", request=req
        )
        await db.commit()
        raise _credentials_exception("Invalid authenticator or recovery code.")

    # Challenge tokens are single-use.
    from packages.utils.jwt import MFA_CHALLENGE_EXPIRE_MINUTES as _TTL
    await revoke_token(
        db,
        jti,
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=_TTL),
    )
    if method == "recovery":
        await security_events.recovery_code_used(db, user.id, req)

    token = create_access_token(
        user_id=user.id,
        credential_version=user.credential_version or 1,
    )
    await security_events.mfa_verification_success(db, user.id, req)
    await security_events.login_success(db, user.id, req)
    await db.commit()

    from config.settings import get_settings
    settings = get_settings()
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/recovery-codes",
    response_model=RecoveryCodesResponse,
    summary="Regenerate one-time recovery codes (requires account password)",
)
async def mfa_recovery_codes(
    payload: MfaRegenerateRequest,
    req: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    if not current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="MFA is not enabled for this account.",
        )
    cred = await _load_credential(db, current_user.id)
    if cred is None or not verify_password(payload.current_password, cred.password_hash):
        raise _credentials_exception("Invalid password.")
    codes = await _persist_recovery_codes(db, current_user.id)
    await security_events.recovery_codes_regenerated(db, current_user.id, req)
    await db.commit()
    return RecoveryCodesResponse(codes=codes)


@router.post(
    "/disable",
    response_model=LoginResultResponse,
    summary="Disable MFA (requires a valid authenticator or recovery code)",
)
async def mfa_disable(
    payload: MfaDisableRequest,
    req: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    if not current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="MFA is not enabled for this account.",
        )
    ok, method = await _verify_second_factor(db, current_user, payload.code)
    if not ok:
        await security_events.mfa_verification_failed(
            db, current_user.id, reason="invalid_disable_code", request=req
        )
        await db.commit()
        raise _credentials_exception("Invalid authenticator or recovery code.")
    if method == "recovery":
        await security_events.recovery_code_used(db, current_user.id, req)

    current_user.mfa_enabled = False
    current_user.mfa_secret_encrypted = None
    await db.execute(
        delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == current_user.id)
    )
    await security_events.mfa_disabled(db, current_user.id, req)
    await db.commit()
    # MFA is now off: issue a normal session so the caller stays signed in.
    from config.settings import get_settings
    settings = get_settings()
    token = create_access_token(
        user_id=current_user.id,
        credential_version=current_user.credential_version or 1,
    )
    return LoginResultResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
