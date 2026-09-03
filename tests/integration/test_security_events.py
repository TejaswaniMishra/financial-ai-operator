import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database.models.security import SecurityEvent, SecurityEventType
from datetime import datetime, timezone, timedelta

pytestmark = pytest.mark.asyncio

async def test_security_events_list_paginated(async_client: AsyncClient, test_user, admin_headers, db_session: AsyncSession):
    # Log an event manually to test the endpoint
    event = SecurityEvent(
        event_type=SecurityEventType.LOGIN_SUCCESS.value,
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
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    
    test_events = [e for e in data["items"] if e["event_type"] == SecurityEventType.LOGIN_SUCCESS.value]
    assert len(test_events) >= 1
    evt = test_events[0]
    
    assert evt["user_id"] == test_user.id
    assert evt["actor_id"] == test_user.id
    assert evt["ip_address"] == "127.0.0.1"
    assert evt["metadata_payload"]["test"] == "data"
    assert evt["is_success"] is True

async def test_security_events_filters(async_client: AsyncClient, test_user, admin_headers, db_session: AsyncSession):
    # Create multiple events
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    e1 = SecurityEvent(event_type=SecurityEventType.LOGIN_FAILURE.value, user_id=test_user.id, is_success=False, created_at=now - timedelta(days=2))
    e2 = SecurityEvent(event_type=SecurityEventType.LOGIN_SUCCESS.value, actor_id=test_user.id, is_success=True, created_at=now - timedelta(days=1))
    e3 = SecurityEvent(event_type=SecurityEventType.LOGIN_SUCCESS.value, user_id=test_user.id, actor_id=test_user.id, is_success=True, created_at=now)
    db_session.add_all([e1, e2, e3])
    await db_session.commit()
    
    # Filter by event type
    res = await async_client.get(f"/api/v1/admin/security-events?event_type={SecurityEventType.LOGIN_FAILURE.value}", headers=admin_headers)
    assert len(res.json()["items"]) == 1
    
    # Filter by is_success
    res = await async_client.get("/api/v1/admin/security-events?is_success=false", headers=admin_headers)
    assert all(not e["is_success"] for e in res.json()["items"])
    
    # Filter by date
    res = await async_client.get(f"/api/v1/admin/security-events?start_time={(now - timedelta(hours=1)).isoformat()}", headers=admin_headers)
    assert len(res.json()["items"]) == 1
    
    # Filter by target
    res = await async_client.get(f"/api/v1/admin/security-events?user_id={test_user.id}", headers=admin_headers)
    assert all(e["user_id"] == test_user.id for e in res.json()["items"])
    
    # Validation errors
    res = await async_client.get("/api/v1/admin/security-events?user_id=invalid_uuid", headers=admin_headers)
    assert res.status_code == 400
    
    res = await async_client.get("/api/v1/admin/security-events?event_type=INVALID_EVENT", headers=admin_headers)
    assert res.status_code == 422 # FastAPI validation for Enums
    
    res = await async_client.get("/api/v1/admin/security-events?limit=5000", headers=admin_headers)
    assert res.status_code == 422

async def test_security_events_append_only(db_session: AsyncSession, test_user):
    event = SecurityEvent(event_type=SecurityEventType.LOGOUT.value, user_id=test_user.id, is_success=True)
    db_session.add(event)
    await db_session.commit()
    await db_session.refresh(event)
    
    event.is_success = False
    with pytest.raises(ValueError, match="append-only"):
        await db_session.commit()
        
    await db_session.rollback()
    
    await db_session.delete(event)
    with pytest.raises(ValueError, match="append-only"):
        await db_session.commit()

async def test_security_events_unauthorized(async_client: AsyncClient, auth_headers):
    response = await async_client.get("/api/v1/admin/security-events")
    assert response.status_code == 401

    response = await async_client.get("/api/v1/admin/security-events", headers=auth_headers)
    assert response.status_code == 403
