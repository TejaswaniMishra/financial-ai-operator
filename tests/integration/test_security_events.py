import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database.models.security import SecurityEvent

pytestmark = pytest.mark.asyncio

async def test_security_events_list(async_client: AsyncClient, test_user, admin_headers, db_session: AsyncSession):
    # Log an event manually to test the endpoint
    event = SecurityEvent(
        event_type="TEST_EVENT",
        user_id=test_user.id,
        actor_id=test_user.id,
        ip_address="127.0.0.1",
        user_agent="pytest",
        is_success=True,
        metadata_payload={"test": "data"}
    )
    db_session.add(event)
    await db_session.commit()
    
    response = await async_client.get("/api/v1/admin/security-events", headers=admin_headers)
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) >= 1
    
    test_events = [e for e in data if e["event_type"] == "TEST_EVENT"]
    assert len(test_events) == 1
    evt = test_events[0]
    
    assert evt["user_id"] == test_user.id
    assert evt["actor_id"] == test_user.id
    assert evt["ip_address"] == "127.0.0.1"
    assert evt["metadata_payload"]["test"] == "data"
    assert evt["is_success"] is True

async def test_security_events_unauthorized(async_client: AsyncClient, auth_headers):
    response = await async_client.get("/api/v1/admin/security-events")
    assert response.status_code == 401

    response = await async_client.get("/api/v1/admin/security-events", headers=auth_headers)
    assert response.status_code == 403
