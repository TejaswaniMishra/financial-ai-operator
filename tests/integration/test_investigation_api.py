import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4
from decimal import Decimal

from database.models.reconciliation import ReconciliationRun, Discrepancy

@pytest.fixture
async def seeded_discrepancy(seeded_db: AsyncSession):
    run_id = str(uuid4())
    run = ReconciliationRun(id=run_id)
    seeded_db.add(run)
    
    disc_id = str(uuid4())
    disc = Discrepancy(
        id=disc_id,
        run_id=run_id,
        rule_code="API_TEST_001",
        discrepancy_type="AMOUNT_MISMATCH",
        severity="HIGH",
        source_entity_type="PAYMENT",
        source_entity_id=str(uuid4()),
        expected_amount=Decimal("500.00"),
        actual_amount=Decimal("450.00"),
        difference_amount=Decimal("50.00"),
        currency="USD"
    )
    seeded_db.add(disc)
    await seeded_db.commit()
    return disc_id

@pytest.mark.asyncio
async def test_investigation_api_run(async_client: AsyncClient, seeded_discrepancy: str):
    response = await async_client.post(f"/api/v1/investigations/discrepancy/{seeded_discrepancy}/run")
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "COMPLETED"
    assert data["is_valid"] is True
    assert "investigation_id" in data
    assert "attempt_id" in data
    
    investigation_id = data["investigation_id"]
    
    # Test GET investigation
    response_get = await async_client.get(f"/api/v1/investigations/{investigation_id}")
    assert response_get.status_code == 200
    data_get = response_get.json()
    assert data_get["discrepancy_id"] == seeded_discrepancy
    assert data_get["status"] == "COMPLETED"
    
    # Test GET attempts
    response_attempts = await async_client.get(f"/api/v1/investigations/{investigation_id}/attempts")
    assert response_attempts.status_code == 200
    attempts = response_attempts.json()
    assert len(attempts) == 1
    assert attempts[0]["model_used"] == "MockLLMProvider"

@pytest.mark.asyncio
async def test_investigation_api_approve(async_client: AsyncClient, seeded_discrepancy: str):
    # Run first
    run_resp = await async_client.post(f"/api/v1/investigations/discrepancy/{seeded_discrepancy}/run")
    investigation_id = run_resp.json()["investigation_id"]
    
    # Approve
    app_resp = await async_client.post(f"/api/v1/investigations/{investigation_id}/approve")
    assert app_resp.status_code == 200
    data = app_resp.json()
    
    assert data["action"] == "APPROVED_ACTION_REQUEST_CREATED"
    assert "No direct financial changes were made" in data["message"]

@pytest.mark.asyncio
async def test_investigation_api_not_found(async_client: AsyncClient):
    response = await async_client.post(f"/api/v1/investigations/discrepancy/invalid-uuid/run")
    assert response.status_code == 404
