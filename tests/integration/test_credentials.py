import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select

from database.models.identity import User, UserCredential
from packages.utils.crypto import hash_password

@pytest.mark.asyncio
async def test_user_credential_creation(db_session: AsyncSession):
    # 1. Create a user
    user = User(email="credential_test@example.com", display_name="Cred Test")
    db_session.add(user)
    await db_session.flush() # flush to get user.id
    
    # 2. Create credential
    pwd_hash = hash_password("ValidPassword123")
    cred = UserCredential(user_id=user.id, password_hash=pwd_hash)
    db_session.add(cred)
    await db_session.commit()
    
    assert cred.id is not None
    assert cred.password_hash == pwd_hash
    assert "ValidPassword123" not in cred.password_hash # Plaintext is not stored
    
@pytest.mark.asyncio
async def test_user_credential_uniqueness(db_session: AsyncSession):
    # 1. Create a user
    user = User(email="unique_cred_test@example.com", display_name="Unique Cred Test")
    db_session.add(user)
    await db_session.flush()
    
    # 2. Create first credential
    cred1 = UserCredential(user_id=user.id, password_hash="hash1")
    db_session.add(cred1)
    await db_session.commit()
    
    # 3. Attempt to create second credential
    cred2 = UserCredential(user_id=user.id, password_hash="hash2")
    db_session.add(cred2)
    
    with pytest.raises(IntegrityError):
        await db_session.commit()
        
    await db_session.rollback()
    
@pytest.mark.asyncio
async def test_user_credential_cascade_delete(db_session: AsyncSession):
    # 1. Create user and credential
    user = User(email="cascade_test@example.com", display_name="Cascade Test")
    db_session.add(user)
    await db_session.flush()
    
    cred = UserCredential(user_id=user.id, password_hash="hash")
    db_session.add(cred)
    await db_session.commit()
    
    cred_id = cred.id
    
    # 2. Delete user
    await db_session.delete(user)
    await db_session.commit()
    
    # 3. Verify credential was deleted via CASCADE
    stmt = select(UserCredential).where(UserCredential.id == cred_id)
    result = await db_session.execute(stmt)
    deleted_cred = result.scalar_one_or_none()
    
    assert deleted_cred is None
