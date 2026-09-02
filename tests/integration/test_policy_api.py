import pytest
import uuid
from httpx import AsyncClient

from database.models.investigation import Investigation, InvestigationStatus

@pytest.fixture
async def sample_investigation(db_session):
    inv_id = str(uuid.uuid4())
    inv = Investigation(
        id=inv_id,
        discrepancy_id=str(uuid.uuid4()),
        status=InvestigationStatus.COMPLETED
    )
    db_session.add(inv)
    await db_session.commit()
    await db_session.refresh(inv)
    return inv

@pytest.mark.asyncio
async def test_evaluate_policy_api(async_client: AsyncClient, sample_investigation, auth_headers):
    response = await async_client.post(
        "/api/v1/policies/evaluate",
        json={
            "investigation_id": sample_investigation.id,
            "action": "RESOLVE_DISCREPANCY"
        }
    , headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "RESOLVE_DISCREPANCY"
    assert data["decision"] == "APPROVAL_REQUIRED"
    assert data["rule_code"] == "POLICY_RESOLUTION_REQUIRES_APPROVAL"
    assert data["approval_required"] is True
    assert "policy_decision_id" in data

@pytest.mark.asyncio
async def test_evaluate_policy_api_not_found(async_client: AsyncClient, db_session, auth_headers):
    response = await async_client.post(
        "/api/v1/policies/evaluate",
        json={
            "investigation_id": "missing_id",
            "action": "RESOLVE_DISCREPANCY"
        }
    , headers=auth_headers)
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_evaluate_policy_api_unsupported_action(async_client: AsyncClient, db_session, auth_headers):
    response = await async_client.post(
        "/api/v1/policies/evaluate",
        json={
            "investigation_id": "some_id",
            "action": "BOGUS_ACTION"
        }
    , headers=auth_headers)
    
    # Pydantic validation should fail this before it hits the engine
    assert response.status_code == 422
