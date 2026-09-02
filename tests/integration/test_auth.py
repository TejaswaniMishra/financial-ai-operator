import pytest
import jwt
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException

from database.models.identity import User, UserCredential, Role, RoleName, UserRole
from packages.utils.crypto import hash_password
from packages.utils.jwt import create_access_token, decode_access_token, JWTError
from apps.api.auth import get_current_user
from fastapi.security import HTTPAuthorizationCredentials
from config.settings import get_settings

settings = get_settings()

@pytest.fixture
async def setup_test_user(db_session: AsyncSession):
    # Setup roles
    stmt = select(Role).where(Role.name == RoleName.OPERATOR)
    role = (await db_session.execute(stmt)).scalar_one_or_none()
    if not role:
        role = Role(name=RoleName.OPERATOR, description="Operator")
        db_session.add(role)
        await db_session.flush()

    user = User(email="loginuser@example.com", display_name="Login User", is_active=True)
    db_session.add(user)
    await db_session.flush()

    pwd_hash = hash_password("ValidPassword123!")
    cred = UserCredential(user_id=user.id, password_hash=pwd_hash)
    ur = UserRole(user_id=user.id, role_id=role.id)
    db_session.add_all([cred, ur])
    await db_session.commit()
    return user

@pytest.fixture
async def inactive_test_user(db_session: AsyncSession):
    user = User(email="inactive@example.com", display_name="Inactive User", is_active=False)
    db_session.add(user)
    await db_session.flush()

    pwd_hash = hash_password("ValidPassword123!")
    cred = UserCredential(user_id=user.id, password_hash=pwd_hash)
    db_session.add(cred)
    await db_session.commit()
    return user

@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient, setup_test_user):
    payload = {"email": "loginuser@example.com", "password": "ValidPassword123!"}
    res = await async_client.post("/api/v1/auth/login", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    # Verify token payload
    token = data["access_token"]
    decoded = jwt.decode(
        token, 
        settings.JWT_SECRET_KEY, 
        algorithms=[settings.JWT_ALGORITHM], 
        audience=settings.JWT_AUDIENCE
    )
    assert decoded["sub"] == setup_test_user.id
    assert "jti" in decoded
    assert decoded["iss"] == settings.JWT_ISSUER
    
    # Check that roles or password hashes are NOT in JWT
    assert "roles" not in decoded
    assert "password_hash" not in decoded

@pytest.mark.asyncio
async def test_login_wrong_password(async_client: AsyncClient, setup_test_user):
    payload = {"email": "loginuser@example.com", "password": "WrongPassword123!"}
    res = await async_client.post("/api/v1/auth/login", json=payload)
    assert res.status_code == 401
    assert "Invalid email or password" in res.text

@pytest.mark.asyncio
async def test_login_unknown_user(async_client: AsyncClient, db_session: AsyncSession):
    payload = {"email": "nobody@example.com", "password": "ValidPassword123!"}
    res = await async_client.post("/api/v1/auth/login", json=payload)
    assert res.status_code == 401
    assert "Invalid email or password" in res.text

@pytest.mark.asyncio
async def test_login_inactive_user(async_client: AsyncClient, inactive_test_user):
    payload = {"email": "inactive@example.com", "password": "ValidPassword123!"}
    res = await async_client.post("/api/v1/auth/login", json=payload)
    assert res.status_code == 401
    assert "Invalid email or password" in res.text
    
@pytest.mark.asyncio
async def test_unique_jti_generated(async_client: AsyncClient, setup_test_user):
    payload = {"email": "loginuser@example.com", "password": "ValidPassword123!"}
    res1 = await async_client.post("/api/v1/auth/login", json=payload)
    res2 = await async_client.post("/api/v1/auth/login", json=payload)
    
    assert res1.status_code == 200, res1.text
    assert res2.status_code == 200, res2.text
    
    token1 = res1.json()["access_token"]
    token2 = res2.json()["access_token"]
    
    decoded1 = jwt.decode(token1, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM], audience=settings.JWT_AUDIENCE)
    decoded2 = jwt.decode(token2, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM], audience=settings.JWT_AUDIENCE)
    
    assert decoded1["jti"] != decoded2["jti"]

@pytest.mark.asyncio
async def test_jwt_validation_failures():
    base_payload = {
        "sub": "123", 
        "iat": datetime.now(timezone.utc), 
        "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
        "iss": settings.JWT_ISSUER, 
        "aud": settings.JWT_AUDIENCE, 
        "jti": "abc"
    }
    
    # 1. Expired token
    expired_payload = {**base_payload, "exp": datetime.now(timezone.utc) - timedelta(minutes=1)}
    expired_token = jwt.encode(expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    with pytest.raises(JWTError, match="expired"):
        decode_access_token(expired_token)

    # 2. Wrong issuer
    wrong_iss_payload = {**base_payload, "iss": "bad-issuer"}
    wrong_iss_token = jwt.encode(wrong_iss_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    with pytest.raises(JWTError, match="issuer"):
        decode_access_token(wrong_iss_token)

    # 3. Missing claim
    missing_claim_payload = {"sub": "123"}
    missing_claim_token = jwt.encode(missing_claim_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    with pytest.raises(JWTError, match="Missing required claim"):
        decode_access_token(missing_claim_token)

    # 4. alg=none attack
    # PyJWT rejects 'none' by default if we restrict to HS256, but let's test it via raw string or bypassing encode
    with pytest.raises(JWTError):
        # Even if someone constructs an alg=none token, decode_access_token forces HS256
        decode_access_token("eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiIxMjMifQ.")
        
    # 5. Invalid signature / modified payload
    valid_token = jwt.encode(base_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    modified_token = valid_token[:-5] + "aaaaa"
    with pytest.raises(JWTError, match="Invalid token"):
        decode_access_token(modified_token)

@pytest.mark.asyncio
async def test_get_current_user_dependency(setup_test_user, db_session: AsyncSession):
    # 1. Valid token
    token = create_access_token(setup_test_user.id)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    
    user = await get_current_user(credentials=creds, db=db_session)
    assert user.id == setup_test_user.id
    assert user.email == "loginuser@example.com"
    
    # 2. Invalid token raises 401
    bad_creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad.token.here")
    with pytest.raises(HTTPException) as exc:
        await get_current_user(credentials=bad_creds, db=db_session)
    assert exc.value.status_code == 401
    
    # 3. Deleted/Non-existent user raises 401
    ghost_token = create_access_token("00000000-0000-0000-0000-000000000000")
    ghost_creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=ghost_token)
    with pytest.raises(HTTPException) as exc:
        await get_current_user(credentials=ghost_creds, db=db_session)
    assert exc.value.status_code == 401

def test_production_secret_fails_fast():
    # Verify that initializing settings in production with default secret raises an error
    from config.settings import Settings
    from config.env import Environment
    
    # This should work in DEV
    Settings(APP_ENV=Environment.DEVELOPMENT, JWT_SECRET_KEY="dev-secret-key-change-me")
    
    # This should fail in PROD
    with pytest.raises(ValueError, match="secure JWT_SECRET_KEY must be explicitly configured"):
        Settings(APP_ENV=Environment.PRODUCTION, JWT_SECRET_KEY="dev-secret-key-change-me")

@pytest.mark.asyncio
async def test_get_me_success(async_client: AsyncClient, setup_test_user):
    token = create_access_token(setup_test_user.id)
    headers = {"Authorization": f"Bearer {token}"}
    res = await async_client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == str(setup_test_user.id)
    assert data["email"] == setup_test_user.email
    assert data["display_name"] == setup_test_user.display_name
    assert data["is_active"] is True
    assert "roles" not in data
    assert "password_hash" not in data
    assert "token" not in data

@pytest.mark.asyncio
async def test_get_me_missing_token(async_client: AsyncClient):
    res = await async_client.get("/api/v1/auth/me")
    assert res.status_code == 401
    
@pytest.mark.asyncio
async def test_get_me_invalid_token(async_client: AsyncClient):
    headers = {"Authorization": "Bearer bad.token.here"}
    res = await async_client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_get_me_inactive_user(async_client: AsyncClient, inactive_test_user):
    token = create_access_token(inactive_test_user.id)
    headers = {"Authorization": f"Bearer {token}"}
    res = await async_client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 401
