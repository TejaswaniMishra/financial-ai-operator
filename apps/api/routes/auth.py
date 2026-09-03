from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from apps.api.dependencies import get_db_session
from apps.api.auth import get_current_user, get_current_user_allow_pending, security
from database.models.identity import User, UserCredential, Role, RoleName, UserRole
from packages.schemas.auth import SignupRequest, LoginRequest, TokenResponse, CurrentUserResponse, LogoutResponse, ChangePasswordRequest, ChangePasswordResponse
from packages.schemas.identity import UserResponse
from packages.utils.crypto import hash_password, verify_password
from packages.utils.password_policy import validate_password
from packages.utils.jwt import create_access_token, decode_access_token
from services.auth.token_revocation import revoke_token
from services.auth.password_management import (
    PasswordPolicyError,
    SamePasswordError,
    WrongCurrentPasswordError,
    change_own_password,
)
from config.settings import get_settings

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

@router.post(
    "/signup", 
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user"
)
async def signup(
    request: SignupRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Registers a new user securely.
    - Validates the password policy
    - Hashes the password with Argon2id
    - Assigns the default safe 'OPERATOR' role
    - Prevents duplicate registrations safely
    """
    # 1. Validate password policy explicitly
    try:
        validate_password(request.password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, 
            detail=str(e)
        )
        
    normalized_email = request.normalize_email()
    
    # 2. Look up the default OPERATOR role
    stmt = select(Role).where(Role.name == RoleName.OPERATOR)
    result = await db.execute(stmt)
    operator_role = result.scalar_one_or_none()
    
    if not operator_role:
        # We fail safely and loudly if the system hasn't seeded the roles.
        # Role seeding remains an administrative responsibility.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="System is not configured to accept registrations at this time."
        )

    # 3. Hash password securely
    pwd_hash = hash_password(request.password)
    
    # 4. Construct user and credential (atomic boundary starts implicitly with session.add)
    user = User(
        email=normalized_email,
        display_name=request.display_name,
        is_active=True
    )
    
    db.add(user)
    
    # We must flush to get the user.id generated before creating related entities
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists."
        )
        
    credential = UserCredential(
        user_id=user.id,
        password_hash=pwd_hash
    )
    
    user_role = UserRole(
        user_id=user.id,
        role_id=operator_role.id
    )
    
    db.add(credential)
    db.add(user_role)
    
    # Commit the transaction completely
    try:
        await db.commit()
    except IntegrityError:
        # Catch-all for any concurrent insertion collisions on roles/credentials
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists."
        )
        
    # Re-query user to eagerly load relationships for the response
    stmt_full = (
        select(User)
        .where(User.id == user.id)
        .options(selectinload(User.roles).selectinload(UserRole.role))
    )
    res_full = await db.execute(stmt_full)
    full_user = res_full.scalar_one()

    return full_user


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Login to get access token"
)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Authenticate user and return a JWT access token.
    - Validates email and password
    - Issues short-lived access token
    - Fails genericly for unknown/wrong/inactive
    """
    generic_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    normalized_email = request.normalize_email()
    
    # Lookup User
    stmt = select(User).where(User.email == normalized_email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    # Generic error if user missing or inactive
    if not user or not user.is_active:
        raise generic_error
        
    # Lookup Credential
    stmt_cred = select(UserCredential).where(UserCredential.user_id == user.id)
    result_cred = await db.execute(stmt_cred)
    cred = result_cred.scalar_one_or_none()
    
    if not cred:
        raise generic_error
        
    # Verify Password
    try:
        is_valid = verify_password(request.password, cred.password_hash)
        if not is_valid:
            raise generic_error
    except Exception:
        raise generic_error
        
    settings = get_settings()
    token = create_access_token(
        user_id=user.id,
        credential_version=user.credential_version or 1,
    )
    
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user"
)
async def get_me(
    current_user: User = Depends(get_current_user_allow_pending),
):
    """
    Returns the currently authenticated user's safe identity profile plus the
    authoritative roles and resolved permissions from the database.

    The response is constructed explicitly so only safe fields are exposed:
    no password hashes, credentials, JWT internals, or authorization
    diagnostics. Roles are DB-authoritative; JWT carries identity only.
    Uses the pending-tolerant dependency so a user flagged
    `must_change_password` (admin reset) can still discover their state and
    reach the forced password-change flow.
    """
    from packages.rbac.matrix import permissions_for_user

    roles = [
        ur.role.name.value for ur in current_user.roles if ur.role is not None
    ]
    permissions = sorted(p.value for p in permissions_for_user(current_user))
    return CurrentUserResponse(
        id=current_user.id,
        email=current_user.email,
        display_name=current_user.display_name,
        is_active=current_user.is_active,
        roles=roles,
        permissions=permissions,
        must_change_password=bool(current_user.must_change_password),
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout current user"
)
async def logout(
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Revokes the currently presented access token.
    Safe and idempotent.
    """
    # The token is already cryptographically validated by get_current_user.
    # We decode it again locally just to extract the payload fields.
    from datetime import datetime, timezone
    
    payload = decode_access_token(credentials.credentials)
    jti = payload.get("jti")
    exp_timestamp = payload.get("exp")
    
    if not jti or not exp_timestamp:
        # Failsafe; decode_access_token already enforced these claims exist
        raise HTTPException(status_code=500, detail="Invalid token structure")
        
    # Convert timestamp to timezone-naive UTC datetime for the database
    expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc).replace(tzinfo=None)
    
    await revoke_token(db, jti, current_user.id, expires_at)
    
    return LogoutResponse(message="Successfully logged out")


@router.post(
    "/change-password",
    response_model=ChangePasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Change the authenticated user's password"
)
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user_allow_pending),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Changes the AUTHENTICATED user's password.

    - current_password is verified against the stored Argon2id hash
    - the centralized password policy applies to new_password
    - the target is always the authenticated user (no user_id accepted)
    - success increments the user's credential version, invalidating every
      existing session/token for this user at once
    - never returns or logs passwords/hashes
    """
    try:
        await change_own_password(
            db,
            current_user,
            request.current_password,
            request.new_password,
        )
    except WrongCurrentPasswordError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        )
    except SamePasswordError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        )
    except PasswordPolicyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )

    return ChangePasswordResponse(
        message="Password changed successfully. All existing sessions have been signed out."
    )
