from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from apps.api.dependencies import get_db_session
from database.models.identity import User, UserRole
from packages.utils.jwt import decode_access_token, JWTError
from services.auth.token_revocation import is_token_revoked

# Standard HTTP Bearer scheme
security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db_session),
    allow_must_change_password: bool = False,
) -> User:
    """
    Validates Bearer token, checks for revocation, extracts user ID, and
    verifies the user is active in the database.

    Security lifecycle (M8.5):
    - Tokens carry the user's `cver` (credential version). A token whose cver
      does not match the user's current DB value was issued before a password
      change/reset and is rejected with 401 — this invalidates ALL previously
      issued sessions at once.
    - When `allow_must_change_password` is False (the default for protected
      business routes), a user flagged `must_change_password` (admin password
      reset pending) is denied with 403 until they change their password.
      Only select endpoints (auth /me, change-password) opt in via
      `get_current_user_allow_pending`.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = decode_access_token(credentials.credentials)
        user_id: str = payload.get("sub")
        jti: str = payload.get("jti")
        if not user_id or not jti:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    # Check revocation explicitly after cryptographic validation but before loading User
    if await is_token_revoked(db, jti):
        raise credentials_exception
        
    # We query the user eagerly loading roles to support future RBAC
    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.roles).selectinload(UserRole.role))
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
        
    if not user.is_active:
        raise credentials_exception

    # Credential-version check: tokens issued under a previous password
    # lifecycle version are stale and must be rejected (401).
    token_version = payload.get("cver")
    if token_version is None or token_version != user.credential_version:
        raise credentials_exception

    # Forced password change: authenticated but restricted until the user
    # changes their password (admin reset flow).
    if user.must_change_password and not allow_must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password change required before accessing this resource.",
        )

    return user


async def get_current_user_allow_pending(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """Authentication dependency that permits users flagged
    `must_change_password` to reach identity/password endpoints (/auth/me,
    change-password) while every other protected route keeps denying them.

    Version, revocation, existence, and active checks still apply.
    """
    return await get_current_user(
        credentials=credentials,
        db=db,
        allow_must_change_password=True,
    )
