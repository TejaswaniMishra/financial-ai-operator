import pytest
import uuid
from sqlalchemy.future import select

from database.models.policy import PolicyAction, PolicyDecision, PolicyEvaluation
from database.models.investigation import Investigation, InvestigationStatus
from services.policy.engine import PolicyEngine

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
async def test_policy_engine_retry_investigation(db_session, sample_investigation):
    engine = PolicyEngine(db_session)
    evaluation = await engine.evaluate(sample_investigation.id, PolicyAction.RETRY_INVESTIGATION)
    
    assert evaluation.action == PolicyAction.RETRY_INVESTIGATION
    assert evaluation.decision == PolicyDecision.ALLOWED
    assert evaluation.rule_code == "POLICY_RETRY_ALLOWED"
    assert evaluation.approval_required is False
    assert evaluation.investigation_id == sample_investigation.id

@pytest.mark.asyncio
async def test_policy_engine_manual_review(db_session, sample_investigation):
    engine = PolicyEngine(db_session)
    evaluation = await engine.evaluate(sample_investigation.id, PolicyAction.REQUEST_MANUAL_REVIEW)
    
    assert evaluation.decision == PolicyDecision.ALLOWED
    assert evaluation.rule_code == "POLICY_MANUAL_REVIEW_ALLOWED"

@pytest.mark.asyncio
async def test_policy_engine_resolve_discrepancy(db_session, sample_investigation):
    engine = PolicyEngine(db_session)
    evaluation = await engine.evaluate(sample_investigation.id, PolicyAction.RESOLVE_DISCREPANCY)
    
    assert evaluation.decision == PolicyDecision.APPROVAL_REQUIRED
    assert evaluation.rule_code == "POLICY_RESOLUTION_REQUIRES_APPROVAL"
    assert evaluation.approval_required is True

@pytest.mark.asyncio
async def test_policy_engine_escalate(db_session, sample_investigation):
    engine = PolicyEngine(db_session)
    evaluation = await engine.evaluate(sample_investigation.id, PolicyAction.ESCALATE)
    
    assert evaluation.decision == PolicyDecision.APPROVAL_REQUIRED
    assert evaluation.rule_code == "POLICY_ESCALATION_REQUIRES_APPROVAL"

@pytest.mark.asyncio
async def test_policy_engine_reject_recommendation(db_session, sample_investigation):
    engine = PolicyEngine(db_session)
    evaluation = await engine.evaluate(sample_investigation.id, PolicyAction.REJECT_RECOMMENDATION)
    
    assert evaluation.decision == PolicyDecision.APPROVAL_REQUIRED
    assert evaluation.rule_code == "POLICY_REJECTION_REQUIRES_APPROVAL"

@pytest.mark.asyncio
async def test_policy_engine_missing_investigation(db_session):
    engine = PolicyEngine(db_session)
    with pytest.raises(ValueError, match="not found"):
        await engine.evaluate("nonexistent_id", PolicyAction.RETRY_INVESTIGATION)

@pytest.mark.asyncio
async def test_policy_engine_persistence(db_session, sample_investigation):
    engine = PolicyEngine(db_session)
    evaluation = await engine.evaluate(sample_investigation.id, PolicyAction.RETRY_INVESTIGATION)
    
    stmt = select(PolicyEvaluation).where(PolicyEvaluation.id == evaluation.id)
    persisted = (await db_session.execute(stmt)).scalar_one_or_none()
    
    assert persisted is not None
    assert persisted.action == PolicyAction.RETRY_INVESTIGATION
    assert persisted.decision == PolicyDecision.ALLOWED

@pytest.mark.asyncio
async def test_policy_engine_idempotency(db_session, sample_investigation):
    engine = PolicyEngine(db_session)
    eval1 = await engine.evaluate(sample_investigation.id, PolicyAction.RETRY_INVESTIGATION)
    eval2 = await engine.evaluate(sample_investigation.id, PolicyAction.RETRY_INVESTIGATION)
    
    # Should return the same persisted record
    assert eval1.id == eval2.id
    
    stmt = select(PolicyEvaluation).where(PolicyEvaluation.investigation_id == sample_investigation.id)
    results = (await db_session.execute(stmt)).scalars().all()
    
    assert len(results) == 1
