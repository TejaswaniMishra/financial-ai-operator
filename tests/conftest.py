import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Force test environment before importing settings/app
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///file:testdb?mode=memory&cache=shared"
os.environ["DATABASE_URL_SYNC"] = "sqlite:///file:testdb?mode=memory&cache=shared"
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
