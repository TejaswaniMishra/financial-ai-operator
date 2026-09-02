import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4
from decimal import Decimal

from database.models.reconciliation import ReconciliationRun, Discrepancy

@pytest.fixture
async def seeded_discrepancy(db_session: AsyncSession):
    run_id = str(uuid4())
    run = ReconciliationRun(id=run_id)
    db_session.add(run)
    
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
    db_session.add(disc)
    await db_session.commit()
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
async def test_investigation_api_not_found(async_client: AsyncClient, db_session):
    response = await async_client.post(f"/api/v1/investigations/discrepancy/invalid-uuid/run")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_investigation_api_get_attempt(async_client: AsyncClient, seeded_discrepancy: str):
    # 1. Run investigation to create attempt
    run_resp = await async_client.post(f"/api/v1/investigations/discrepancy/{seeded_discrepancy}/run")
    assert run_resp.status_code == 200
    run_data = run_resp.json()

    investigation_id = run_data["investigation_id"]
    attempt_id = run_data["attempt_id"]

    # 2. Get specific attempt successfully
    get_resp = await async_client.get(f"/api/v1/investigations/{investigation_id}/attempts/{attempt_id}")
    assert get_resp.status_code == 200

    attempt_data = get_resp.json()
    assert attempt_data["investigation_id"] == investigation_id
    assert attempt_data["attempt_id"] == attempt_id
    assert attempt_data["status"] == run_data["status"]
    assert attempt_data["is_valid"] == run_data["is_valid"]

    # Check that 'result' comes from validated_output and 'errors' from validation_errors
    assert "result" in attempt_data
    if run_data["is_valid"]:
        assert attempt_data["result"] is not None
        assert attempt_data["errors"] is None
    else:
        assert attempt_data["result"] is None
        assert attempt_data["errors"] is not None

    # Check that internal fields are NOT exposed
    assert "context_snapshot" not in attempt_data
    assert "context_hash" not in attempt_data
    assert "raw_llm_response" not in attempt_data

    # 3. Test non-existent attempt
    bad_attempt_id = str(uuid4())
    bad_resp = await async_client.get(f"/api/v1/investigations/{investigation_id}/attempts/{bad_attempt_id}")
    assert bad_resp.status_code == 404
    assert "Investigation attempt not found" in bad_resp.json()["detail"]

    # 4. Test existing attempt with wrong investigation_id
    bad_investigation_id = str(uuid4())
    wrong_inv_resp = await async_client.get(f"/api/v1/investigations/{bad_investigation_id}/attempts/{attempt_id}")
    assert wrong_inv_resp.status_code == 404
    assert "Investigation attempt not found" in wrong_inv_resp.json()["detail"]
