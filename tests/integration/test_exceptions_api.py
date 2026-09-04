import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from database.seed_data.generator import DataGenerator
from database.models import Investigation, PolicyEvaluation, ActionRequest, ActionExecution, Discrepancy
from packages.schemas.action_request import ActionRequestStatus
from packages.schemas.action_execution import ActionExecutionStatus
from packages.schemas.policy import PolicyDecision, PolicyAction
from database.models.investigation import InvestigationStatus
import uuid
import datetime

@pytest.fixture
async def seeded_db_with_exceptions(db_session: AsyncSession):
    generator = DataGenerator(db_session)
    await generator.generate()
    
    # Generate exceptions by triggering reconciliation
    # We should have discrepancies now
    from packages.schemas.reconciliation import DiscrepancyType, Severity
    disc = Discrepancy(
        id=str(uuid.uuid4()),
        run_id=str(uuid.uuid4()),
        rule_code="TEST",
        discrepancy_type=DiscrepancyType.FEE_MISMATCH,
        severity=Severity.HIGH,
        source_entity_type="PAYMENT",
        source_entity_id="test-payment",
    )
    db_session.add(disc)
    await db_session.flush()
    
    # Create an investigation
    inv = Investigation(
        id=str(uuid.uuid4()),
        discrepancy_id=disc.id,
        status=InvestigationStatus.COMPLETED
    )
    db_session.add(inv)
    await db_session.flush()
    
    # Create a policy evaluation
    pol = PolicyEvaluation(
        id=str(uuid.uuid4()),
        investigation_id=inv.id,
        discrepancy_id=disc.id,
        action=PolicyAction.REQUEST_MANUAL_REVIEW,
        decision=PolicyDecision.APPROVAL_REQUIRED,
        rule_code="TEST_RULE",
        reason="Test reason"
    )
    db_session.add(pol)
    await db_session.flush()
    
    # Create action request
    req = ActionRequest(
        id=str(uuid.uuid4()),
        investigation_id=inv.id,
        discrepancy_id=disc.id,
        policy_evaluation_id=pol.id,
        action="TEST_ACTION",
        status=ActionRequestStatus.APPROVED
    )
    db_session.add(req)
    await db_session.flush()
    
    # Create action execution
    exec_ = ActionExecution(
        id=str(uuid.uuid4()),
        action_request_id=req.id,
        idempotency_key=str(uuid.uuid4()),
        status=ActionExecutionStatus.RUNNING,
        execution_type="test",
        adapter="test"
    )
    db_session.add(exec_)
    
    await db_session.commit()
    
    return db_session, disc.id

@pytest.mark.asyncio
async def test_exceptions_list_api(async_client: AsyncClient, seeded_db_with_exceptions, auth_headers):
    db_session, expected_disc_id = seeded_db_with_exceptions
    
    response = await async_client.get("/api/v1/exceptions", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    
    # Check the state of the one we mutated
    item = next((i for i in data["items"] if i["id"] == expected_disc_id), None)
    assert item is not None
    assert item["overall_state"] == "EXECUTING"

@pytest.mark.asyncio
async def test_exceptions_detail_api(async_client: AsyncClient, seeded_db_with_exceptions, auth_headers):
    db_session, expected_disc_id = seeded_db_with_exceptions
    
    response = await async_client.get(f"/api/v1/exceptions/{expected_disc_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == expected_disc_id
    assert data["overall_state"] == "EXECUTING"
    assert data["investigation_status"] == "COMPLETED"
    assert data["policy_decision"] == "APPROVAL_REQUIRED"
    assert data["action_request_status"] == "APPROVED"
    assert data["execution_status"] == "RUNNING"
