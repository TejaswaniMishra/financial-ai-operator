import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database.models.identity import User, UserCredential, UserRole, Role, RoleName

@pytest.fixture
async def seeded_operator_role(db_session: AsyncSession):
    # Ensure OPERATOR role exists for tests
    stmt = select(Role).where(Role.name == RoleName.OPERATOR)
    result = await db_session.execute(stmt)
    role = result.scalar_one_or_none()
    if not role:
        role = Role(name=RoleName.OPERATOR, description="Operator")
        db_session.add(role)
        await db_session.commit()
    return role

@pytest.mark.asyncio
async def test_signup_success(async_client: AsyncClient, seeded_operator_role, db_session: AsyncSession):
    payload = {
        "email": "NeWUser@eXaMple.com",
        "password": "StrongPassword123!",
        "display_name": "New User"
    }
    
    response = await async_client.post("/api/v1/auth/signup", json=payload)
    assert response.status_code == 201
    
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["display_name"] == "New User"
    assert data["is_active"] is True
    
    # Sensitive data is excluded
    assert "password" not in data
    assert "password_hash" not in data
    
    # Verify DB state
    stmt = select(User).where(User.email == "newuser@example.com")
    result = await db_session.execute(stmt)
    user = result.scalar_one()
    
    stmt_cred = select(UserCredential).where(UserCredential.user_id == user.id)
    result_cred = await db_session.execute(stmt_cred)
    cred = result_cred.scalar_one()
    
    assert cred.password_hash != "StrongPassword123!"
    assert "$argon2id$" in cred.password_hash
    
    # Verify role
    stmt_role = select(UserRole).where(UserRole.user_id == user.id)
    result_role = await db_session.execute(stmt_role)
    ur = result_role.scalar_one()
    assert ur.role_id == seeded_operator_role.id

@pytest.mark.asyncio
async def test_signup_duplicate_email(async_client: AsyncClient, seeded_operator_role):
    payload = {
        "email": "duplicate@example.com",
        "password": "StrongPassword123!",
        "display_name": "User 1"
    }
    # First signup
    res1 = await async_client.post("/api/v1/auth/signup", json=payload)
    assert res1.status_code == 201
    
    # Second signup
    res2 = await async_client.post("/api/v1/auth/signup", json=payload)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]

@pytest.mark.asyncio
async def test_signup_invalid_password(async_client: AsyncClient, seeded_operator_role):
    payload = {
        "email": "weak@example.com",
        "password": "short",
        "display_name": "User"
    }
    res = await async_client.post("/api/v1/auth/signup", json=payload)
    assert res.status_code == 422
    # Pydantic validates length
    assert "String should have at least 12 characters" in res.text

@pytest.mark.asyncio
async def test_signup_invalid_email(async_client: AsyncClient, seeded_operator_role):
    payload = {
        "email": "not-an-email",
        "password": "StrongPassword123!",
        "display_name": "User"
    }
    res = await async_client.post("/api/v1/auth/signup", json=payload)
    assert res.status_code == 422
    assert "String should match pattern" in res.text

@pytest.mark.asyncio
async def test_signup_concurrent_race(async_client: AsyncClient, seeded_operator_role, db_session: AsyncSession):
    # Simulate true concurrency
    # We send N requests to the signup endpoint simultaneously
    payload = {
        "email": "race@example.com",
        "password": "StrongPassword123!",
        "display_name": "Race User"
    }
    
    tasks = [async_client.post("/api/v1/auth/signup", json=payload) for _ in range(5)]
    responses = await asyncio.gather(*tasks)
    
    status_codes = [r.status_code for r in responses]
    
    # Exactly one should succeed, others should be 409
    assert status_codes.count(201) == 1
    assert status_codes.count(409) == 4
    
    # Verify DB state cleanly has 1 user and 1 credential
    stmt = select(User).where(User.email == "race@example.com")
    result = await db_session.execute(stmt)
    users = result.scalars().all()
    assert len(users) == 1
    
    stmt_cred = select(UserCredential).where(UserCredential.user_id == users[0].id)
    result_cred = await db_session.execute(stmt_cred)
    creds = result_cred.scalars().all()
    assert len(creds) == 1

    stmt_role = select(UserRole).where(UserRole.user_id == users[0].id)
    result_role = await db_session.execute(stmt_role)
    roles = result_role.scalars().all()
    assert len(roles) == 1
