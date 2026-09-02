from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from apps.api.dependencies import get_db_session
from database.models.identity import User, UserCredential, Role, RoleName, UserRole
from packages.schemas.auth import SignupRequest, LoginRequest, TokenResponse
from packages.schemas.identity import UserResponse
from packages.utils.crypto import hash_password, verify_password
from packages.utils.password_policy import validate_password
from packages.utils.jwt import create_access_token
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
    token = create_access_token(user_id=user.id)
    
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
