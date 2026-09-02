import pytest
import asyncio
from fastapi import status
from sqlalchemy.future import select
from database.models.action_request import ActionRequestStatus
from database.models.action_execution import ActionExecutionStatus
from database.models.policy import PolicyEvaluation, PolicyDecision, PolicyAction
from database.models.investigation import Investigation, InvestigationStatus

pytestmark = pytest.mark.asyncio

@pytest.fixture
async def sample_investigation(db_session):
    import uuid
    inv = Investigation(
        id=str(uuid.uuid4()),
        discrepancy_id=str(uuid.uuid4()),
        status=InvestigationStatus.COMPLETED
    )
    db_session.add(inv)
    await db_session.commit()
    await db_session.refresh(inv)
    return inv

async def create_unique_policy_eval(db_session, sample_investigation):
    import uuid
    eval = PolicyEvaluation(
        id=str(uuid.uuid4()),
        investigation_id=sample_investigation.id,
        discrepancy_id=sample_investigation.discrepancy_id,
        action=PolicyAction.RESOLVE_DISCREPANCY,
        decision=PolicyDecision.APPROVAL_REQUIRED,
        rule_code="TEST_RULE",
        reason="test",
        approval_required=True
    )
    db_session.add(eval)
    await db_session.commit()
    await db_session.refresh(eval)
    return eval

async def test_execute_pending_request_denied(async_client, db_session, sample_investigation, auth_headers):
    eval1 = await create_unique_policy_eval(db_session, sample_investigation)
    # Create PENDING request
    response = await async_client.post("/api/v1/action-requests", json={
        "policy_evaluation_id": eval1.id,
        "requested_source": "test"
    }, headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    request_id = response.json()["id"]
    
    # Try execute
    exec_response = await async_client.post(f"/api/v1/action-requests/{request_id}/execute", json={"idempotency_key": "test_1"}, headers=auth_headers)
    assert exec_response.status_code == status.HTTP_400_BAD_REQUEST
    assert "cannot be executed. Status is PENDING_APPROVAL" in exec_response.json()["detail"]

async def test_execute_approved_request_success(async_client, db_session, sample_investigation, auth_headers):
    eval2 = await create_unique_policy_eval(db_session, sample_investigation)
    # Create request
    response = await async_client.post("/api/v1/action-requests", json={
        "policy_evaluation_id": eval2.id,
        "requested_source": "test"
    }, headers=auth_headers)
    request_id = response.json()["id"]
    
    # Approve request
    approve_resp = await async_client.post(f"/api/v1/action-requests/{request_id}/approve", json={"actor": "test"}, headers=auth_headers)
    assert approve_resp.status_code == status.HTTP_200_OK
    
    # Execute request
    exec_response = await async_client.post(f"/api/v1/action-requests/{request_id}/execute", json={"idempotency_key": "test_success"}, headers=auth_headers)
    assert exec_response.status_code == status.HTTP_200_OK
    
    data = exec_response.json()
    assert data["status"] == "SUCCEEDED"
    assert data["adapter"] == "simulator"
    assert data["idempotency_key"] == "test_success"
    assert len(data["attempts"]) == 1
    assert data["attempts"][0]["status"] == "SUCCEEDED"
    assert data["result"]["outcome"] == "SUCCEEDED"

async def test_execute_simulator_failure(async_client, db_session, sample_investigation, auth_headers):
    eval3 = await create_unique_policy_eval(db_session, sample_investigation)
    # Create and approve second request
    response = await async_client.post("/api/v1/action-requests", json={
        "policy_evaluation_id": eval3.id,
        "requested_source": "test"
    }, headers=auth_headers)
    request_id = response.json()["id"]
    await async_client.post(f"/api/v1/action-requests/{request_id}/approve", json={"actor": "test"}, headers=auth_headers)
    
    # Execute request with fail key
    exec_response = await async_client.post(f"/api/v1/action-requests/{request_id}/execute", json={"idempotency_key": "test_simulate_fail"}, headers=auth_headers)
    assert exec_response.status_code == status.HTTP_200_OK
    
    data = exec_response.json()
    assert data["status"] == "FAILED"
    assert data["error_code"] == "SIMULATED_FAILURE"
    assert len(data["attempts"]) == 1
    assert data["attempts"][0]["status"] == "FAILED"

async def test_execute_simulator_unknown(async_client, db_session, sample_investigation, auth_headers):
    eval4 = await create_unique_policy_eval(db_session, sample_investigation)
    # Create and approve third request
    response = await async_client.post("/api/v1/action-requests", json={
        "policy_evaluation_id": eval4.id,
        "requested_source": "test"
    }, headers=auth_headers)
    request_id = response.json()["id"]
    await async_client.post(f"/api/v1/action-requests/{request_id}/approve", json={"actor": "test"}, headers=auth_headers)
    
    # Execute request with unknown key
    exec_response = await async_client.post(f"/api/v1/action-requests/{request_id}/execute", json={"idempotency_key": "test_simulate_unknown"}, headers=auth_headers)
    assert exec_response.status_code == status.HTTP_200_OK
    
    data = exec_response.json()
    assert data["status"] == "UNKNOWN"
    assert data["error_code"] == "SIMULATED_TIMEOUT"
    
    # Try to execute again (should be blocked from auto-retry because it's UNKNOWN, but idempotency returns the existing execution)
    exec_response_2 = await async_client.post(f"/api/v1/action-requests/{request_id}/execute", json={"idempotency_key": "test_simulate_unknown"}, headers=auth_headers)
    assert exec_response_2.status_code == status.HTTP_200_OK
    data2 = exec_response_2.json()
    assert data2["status"] == "UNKNOWN"

async def test_execution_concurrency_and_idempotency(async_client, db_session, sample_investigation, auth_headers):
    eval5 = await create_unique_policy_eval(db_session, sample_investigation)
    """
    Test idempotency: two sequential execution attempts with the same idempotency key
    result in exactly ONE execution running/completing, and the second reusing it.
    """
    response = await async_client.post("/api/v1/action-requests", json={
        "policy_evaluation_id": eval5.id,
        "requested_source": "test"
    }, headers=auth_headers)
    request_id = response.json()["id"]
    await async_client.post(f"/api/v1/action-requests/{request_id}/approve", json={"actor": "test"}, headers=auth_headers)

    idempotency_key = "concurrent_test_key"

    # Fire both requests concurrently
    req1, req2 = await asyncio.gather(
        async_client.post(f"/api/v1/action-requests/{request_id}/execute", json={"idempotency_key": idempotency_key}, headers=auth_headers),
        async_client.post(f"/api/v1/action-requests/{request_id}/execute", json={"idempotency_key": idempotency_key}, headers=auth_headers)
    )

    assert req1.status_code == status.HTTP_200_OK
    assert req2.status_code == status.HTTP_200_OK
    
    data1 = req1.json()
    data2 = req2.json()
    
    assert data1["id"] == data2["id"]
    assert data1["status"] == "SUCCEEDED"
    
    # Verify exactly one execution in DB
    executions_resp = await async_client.get(f"/api/v1/action-requests/{request_id}/executions", headers=auth_headers)
    executions = executions_resp.json()
    assert len(executions) == 1
    assert executions[0]["status"] == "SUCCEEDED"
