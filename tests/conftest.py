import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Force test environment before importing settings/app
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DATABASE_URL_SYNC"] = "sqlite:///:memory:"
os.environ["DEBUG"] = "false"

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
