from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from apps.api.dependencies import get_db_session
from database.models.identity import User, UserCredential, Role, RoleName, UserRole
from packages.schemas.auth import SignupRequest
from packages.schemas.identity import UserResponse
from packages.utils.crypto import hash_password
from packages.utils.password_policy import validate_password

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
