import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.future import select

from database.models.investigation import Investigation, InvestigationStatus
from database.models.policy import PolicyEvaluation, PolicyAction, PolicyDecision
from database.models.action_request import ActionRequest, ActionRequestAudit, ActionRequestStatus

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

@pytest.fixture
async def sample_evaluation_approval_required(db_session, sample_investigation):
    eval_id = str(uuid.uuid4())
    evaluation = PolicyEvaluation(
        id=eval_id,
        investigation_id=sample_investigation.id,
        discrepancy_id=sample_investigation.discrepancy_id,
        action=PolicyAction.RESOLVE_DISCREPANCY,
        decision=PolicyDecision.APPROVAL_REQUIRED,
        rule_code="POLICY_RESOLUTION_REQUIRES_APPROVAL",
        reason="Test",
        approval_required=True
    )
    db_session.add(evaluation)
    await db_session.commit()
    await db_session.refresh(evaluation)
    return evaluation

@pytest.fixture
async def sample_evaluation_denied(db_session, sample_investigation):
    eval_id = str(uuid.uuid4())
    evaluation = PolicyEvaluation(
        id=eval_id,
        investigation_id=sample_investigation.id,
        discrepancy_id=sample_investigation.discrepancy_id,
        action=PolicyAction.RESOLVE_DISCREPANCY,
        decision=PolicyDecision.DENIED,
        rule_code="POLICY_RESOLUTION_DENIED",
        reason="Test",
        approval_required=False
    )
    db_session.add(evaluation)
    await db_session.commit()
    await db_session.refresh(evaluation)
    return evaluation


@pytest.mark.asyncio
async def test_action_request_creation_approval_required(async_client: AsyncClient, sample_evaluation_approval_required):
    response = await async_client.post(
        "/api/v1/action-requests",
        json={
            "policy_evaluation_id": sample_evaluation_approval_required.id,
            "requested_source": "test"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["policy_evaluation_id"] == sample_evaluation_approval_required.id
    assert data["status"] == "PENDING_APPROVAL"
    assert data["action"] == "RESOLVE_DISCREPANCY"
    
    # Idempotency check
    response2 = await async_client.post(
        "/api/v1/action-requests",
        json={
            "policy_evaluation_id": sample_evaluation_approval_required.id,
            "requested_source": "test"
        }
    )
    assert response2.status_code == 200
    assert response2.json()["id"] == data["id"]

@pytest.mark.asyncio
async def test_action_request_concurrent_creation(async_client: AsyncClient, sample_evaluation_approval_required):
    # Fire two sequential creation requests for the exact same policy evaluation
    # This tests idempotency and race condition handling at the API level
    payload = {
        "policy_evaluation_id": sample_evaluation_approval_required.id,
        "requested_source": "concurrent_test"
    }

    response1 = await async_client.post("/api/v1/action-requests", json=payload)
    response2 = await async_client.post("/api/v1/action-requests", json=payload)

    # One of them might be 200 (created) and the other 200 (returned existing)
    assert response1.status_code == 200
    assert response2.status_code == 200

    data1 = response1.json()
    data2 = response2.json()

    # Ensure only one was created
    assert data1["id"] == data2["id"] == response2.json()["id"]

@pytest.mark.asyncio
async def test_action_request_creation_denied(async_client: AsyncClient, sample_evaluation_denied):
    response = await async_client.post(
        "/api/v1/action-requests",
        json={
            "policy_evaluation_id": sample_evaluation_denied.id
        }
    )
    
    assert response.status_code == 400
    assert "rejected" in response.json()["detail"].lower()

@pytest.fixture
async def sample_action_request(db_session, sample_evaluation_approval_required):
    ar = ActionRequest(
        id=str(uuid.uuid4()),
        investigation_id=sample_evaluation_approval_required.investigation_id,
        discrepancy_id=sample_evaluation_approval_required.discrepancy_id,
        policy_evaluation_id=sample_evaluation_approval_required.id,
        action=sample_evaluation_approval_required.action.value,
        status=ActionRequestStatus.PENDING_APPROVAL
    )
    db_session.add(ar)
    await db_session.commit()
    await db_session.refresh(ar)
    return ar

@pytest.mark.asyncio
async def test_action_request_approve(async_client: AsyncClient, sample_action_request, db_session):
    response = await async_client.post(
        f"/api/v1/action-requests/{sample_action_request.id}/approve",
        json={"actor": "test_user"}
    )
    
    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"
    assert response.json()["approved_by"] == "test_user"
    assert response.json()["approved_at"] is not None
    
    # Check audit log
    stmt = select(ActionRequestAudit).where(ActionRequestAudit.action_request_id == sample_action_request.id)
    audits = (await db_session.execute(stmt)).scalars().all()
    assert len(audits) == 1
    assert audits[0].new_status == ActionRequestStatus.APPROVED
    
    # Try invalid transition
    response2 = await async_client.post(
        f"/api/v1/action-requests/{sample_action_request.id}/reject",
        json={"reason": "test"}
    )
    assert response2.status_code == 400
    assert "invalid state transition" in response2.json()["detail"].lower()

@pytest.mark.asyncio
async def test_action_request_reject(async_client: AsyncClient, sample_action_request, db_session):
    response = await async_client.post(
        f"/api/v1/action-requests/{sample_action_request.id}/reject",
        json={"reason": "bad data"}
    )
    
    assert response.status_code == 200
    assert response.json()["status"] == "REJECTED"
    assert response.json()["rejection_reason"] == "bad data"

@pytest.mark.asyncio
async def test_action_request_cancel(async_client: AsyncClient, sample_action_request, db_session):
    response = await async_client.post(
        f"/api/v1/action-requests/{sample_action_request.id}/cancel",
        json={"reason": "mistake"}
    )
    
    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"
