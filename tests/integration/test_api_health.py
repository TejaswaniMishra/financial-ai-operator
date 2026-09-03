import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "Financial AI Operator"
    assert data["health"] == "/health"


@pytest.mark.asyncio
async def test_health_check_endpoint(async_client: AsyncClient):
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "version" in data
    assert "environment" in data
    assert "database" in data
    assert data["database"]["connected"] is True


@pytest.mark.asyncio
async def test_versioned_health_endpoint(async_client: AsyncClient):
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["database"]["connected"] is True


@pytest.mark.asyncio
async def test_system_info_endpoint(async_client: AsyncClient, auth_headers):
    # M8.3: /system/info is now protected behind VIEW_SETTINGS (all roles have it)
    response = await async_client.get("/api/v1/system/info", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Financial AI Operator"
    assert "active_services" in data
    assert data["active_services"]["api_gateway"] == "healthy"
    assert data["uptime_seconds"] >= 0
