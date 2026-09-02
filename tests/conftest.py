import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Force test environment before importing settings/app
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///testdb.sqlite"
os.environ["DATABASE_URL_SYNC"] = "sqlite:///testdb.sqlite"
os.environ["DEBUG"] = "false"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["LLM_API_KEY"] = ""

from apps.api.main import app
from config.settings import get_settings


@pytest.fixture(autouse=True)
def reset_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

@pytest_asyncio.fixture
async def db_session():
    from database.connection import async_engine, AsyncSessionLocal
    from database.base import Base
    import database.models  # Ensure all models are registered with Base.metadata
    
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with AsyncSessionLocal() as session:
        yield session
        
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture
async def auth_headers(db_session):
    from database.models.identity import User, UserCredential, Role, RoleName, UserRole
    from packages.utils.crypto import hash_password
    from packages.utils.jwt import create_access_token
    from sqlalchemy.future import select
    
    # 1. Create or get Operator role
    stmt = select(Role).where(Role.name == RoleName.OPERATOR)
    res = await db_session.execute(stmt)
    role = res.scalar_one_or_none()
    if not role:
        role = Role(name=RoleName.OPERATOR, description="Operator")
        db_session.add(role)
        await db_session.commit()
        await db_session.refresh(role)
        
    # 2. Create Active User
    user = User(
        email="test_auth@example.com",
        display_name="Test Auth User",
        is_active=True
    )
    db_session.add(user)
    await db_session.flush()
    
    # 3. Create Credential and Role mapping
    pwd_hash = hash_password("ValidPassword123!")
    cred = UserCredential(user_id=user.id, password_hash=pwd_hash)
    user_role = UserRole(user_id=user.id, role_id=role.id)
    db_session.add(cred)
    db_session.add(user_role)
    await db_session.commit()
    
    # 4. Generate Token
    token = create_access_token(user_id=user.id)
    return {"Authorization": f"Bearer {token}"}
