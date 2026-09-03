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
    db: AsyncSession = Depends(get_db_session)
) -> User:
    """
    Validates Bearer token, checks for revocation, extracts user ID, 
    and verifies the user is active in the database.
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
        
    return user
