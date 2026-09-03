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
from database.models.identity import RoleName


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

    # Seed the fixed role vocabulary (idempotent) so tests always have the
    # full OPERATOR / FINANCE_MANAGER / ADMIN set available.
    from sqlalchemy.future import select as _select
    from database.models.identity import Role, RoleName

    async with AsyncSessionLocal() as session:
        for role_name in RoleName:
            stmt = _select(Role).where(Role.name == role_name)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing is None:
                session.add(Role(name=role_name, description=f"{role_name.value} role"))
        await session.commit()

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


async def _make_role_user(db_session, role: RoleName, email: str, display_name: str):
    """Create (idempotently) a role row and a fresh user holding it."""
    from database.models.identity import Role, User, UserCredential, UserRole
    from packages.utils.crypto import hash_password
    from packages.utils.jwt import create_access_token
    from sqlalchemy.future import select

    stmt = select(Role).where(Role.name == role)
    res = await db_session.execute(stmt)
    role_row = res.scalar_one_or_none()
    if not role_row:
        role_row = Role(name=role, description=role.value)
        db_session.add(role_row)
        await db_session.commit()
        await db_session.refresh(role_row)

    user = User(email=email, display_name=display_name, is_active=True)
    db_session.add(user)
    await db_session.flush()

    pwd_hash = hash_password("ValidPassword123!")
    cred = UserCredential(user_id=user.id, password_hash=pwd_hash)
    user_role = UserRole(user_id=user.id, role_id=role_row.id)
    db_session.add_all([cred, user_role])
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    return user, {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def finance_manager_headers(db_session):
    """Authenticated FINANCE_MANAGER user with a valid Bearer token."""
    from database.models.identity import RoleName

    _, headers = await _make_role_user(
        db_session, RoleName.FINANCE_MANAGER, "fm_rbac@example.com", "Finance Manager User"
    )
    return headers


@pytest_asyncio.fixture
async def admin_headers(db_session):
    """Authenticated ADMIN user with a valid Bearer token."""
    from database.models.identity import RoleName

    _, headers = await _make_role_user(
        db_session, RoleName.ADMIN, "admin_rbac@example.com", "Admin User"
    )
    return headers


@pytest_asyncio.fixture
async def operator_headers(db_session):
    """Authenticated OPERATOR user with a valid Bearer token (dedicated user)."""
    from database.models.identity import RoleName

    _, headers = await _make_role_user(
        db_session, RoleName.OPERATOR, "operator_rbac@example.com", "Operator User"
    )
    return headers


@pytest_asyncio.fixture
async def make_role_user(db_session):
    """Factory: create a DB-backed user holding one role, return (user, headers)."""
    from database.models.identity import RoleName

    async def _make(role: RoleName, email: str, display_name: str = "Role User"):
        return await _make_role_user(db_session, role, email, display_name)

    return _make


# Alias async_client as client for compatibility with tests
@pytest_asyncio.fixture
async def client(async_client):
    return async_client


# Fixture providing a test user for token lifecycle tests
@pytest_asyncio.fixture
async def test_user(db_session):
    from database.models.identity import User, UserCredential, Role, RoleName, UserRole
    from packages.utils.crypto import hash_password
    from sqlalchemy.future import select

    # Ensure Operator role exists
    stmt = select(Role).where(Role.name == RoleName.OPERATOR)
    res = await db_session.execute(stmt)
    role = res.scalar_one_or_none()
    if not role:
        role = Role(name=RoleName.OPERATOR, description="Operator")
        db_session.add(role)
        await db_session.flush()
        await db_session.refresh(role)

    # Create a new active user
    user = User(
        email="lifecycle_user@example.com",
        display_name="Lifecycle User",
        is_active=True
    )
    db_session.add(user)
    await db_session.flush()

    # Credential and role mapping
    pwd_hash = hash_password("ValidPassword123!")
    cred = UserCredential(user_id=user.id, password_hash=pwd_hash)
    user_role = UserRole(user_id=user.id, role_id=role.id)
    db_session.add_all([cred, user_role])
    await db_session.commit()
    await db_session.refresh(user)
    return user
