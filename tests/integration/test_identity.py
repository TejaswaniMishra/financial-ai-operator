import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from database.models.identity import User, Role, UserRole, RoleName

@pytest.mark.asyncio
async def test_user_creation_and_email_uniqueness(db_session: AsyncSession):
    # 1. Create a user
    user1 = User(email="test1@example.com", display_name="Test User 1")
    db_session.add(user1)
    await db_session.commit()
    
    assert user1.id is not None
    assert user1.is_active is True
    
    # 2. Try to create another user with the same email
    user2 = User(email="test1@example.com", display_name="Test User 2")
    db_session.add(user2)
    
    with pytest.raises(IntegrityError):
        await db_session.commit()
        
    await db_session.rollback()

@pytest.mark.asyncio
async def test_role_creation_and_uniqueness(db_session: AsyncSession):
    stmt = select(Role).where(Role.name == RoleName.OPERATOR)
    existing = (await db_session.execute(stmt)).scalar_one_or_none()
    
    if not existing:
        role = Role(name=RoleName.OPERATOR)
        db_session.add(role)
        await db_session.commit()
        
    # Explicitly duplicate it
    duplicate_role = Role(name=RoleName.OPERATOR)
    db_session.add(duplicate_role)
    with pytest.raises(IntegrityError):
        await db_session.commit()
        
    await db_session.rollback()

@pytest.mark.asyncio
async def test_user_role_uniqueness_constraint(db_session: AsyncSession):
    # 1. Create User
    user = User(email="roleuser@example.com", display_name="Role User")
    db_session.add(user)
    
    # 2. Get or Create Role
    stmt = select(Role).where(Role.name == RoleName.FINANCE_MANAGER)
    role = (await db_session.execute(stmt)).scalar_one_or_none()
    if not role:
        role = Role(name=RoleName.FINANCE_MANAGER)
        db_session.add(role)
        
    await db_session.commit()
    
    # 3. Assign Role to User
    ur1 = UserRole(user_id=user.id, role_id=role.id)
    db_session.add(ur1)
    await db_session.commit()
    
    assert ur1.id is not None
    
    # 4. Attempt Duplicate Assignment
    ur2 = UserRole(user_id=user.id, role_id=role.id)
    db_session.add(ur2)
    
    with pytest.raises(IntegrityError):
        await db_session.commit()
        
    await db_session.rollback()
