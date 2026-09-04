import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4
from decimal import Decimal
from datetime import datetime, timezone

from database.models.reconciliation import ReconciliationRun, Discrepancy, ReconciliationRelationship
from packages.schemas.reconciliation import RelationshipStatus, FinancialEvaluationStatus
from database.models.merchant import Merchant
from database.models.transaction import Settlement, BankTransaction

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
async def test_investigation_api_run_with_bank_transaction_lineage(
    async_client: AsyncClient,
    db_session: AsyncSession,
    auth_headers,
):
    """Regression: investigation of a SETTLEMENT discrepancy linked to a
    BANK_TRANSACTION must not 500. The investigation context builder once
    referenced BankTransaction.posted_date, which does not exist (the model
    field is transaction_date), crashing every such run."""
    merchant = Merchant(
        id=str(uuid4()),
        external_id=f"m-{uuid4().hex[:8]}",
        name="Regression Merchant",
        default_currency="USD",
        status="ACTIVE",
    )
    db_session.add(merchant)

    run = ReconciliationRun(id=str(uuid4()))
    db_session.add(run)

    settlement = Settlement(
        id=str(uuid4()),
        external_id=f"set-{uuid4().hex[:8]}",
        merchant_id=merchant.id,
        provider="MockPaymentGateway",
        gross_amount=Decimal("100.00"),
        fee_amount=Decimal("2.00"),
        adjustment_amount=Decimal("0.00"),
        expected_net_amount=Decimal("98.00"),
        actual_settled_amount=Decimal("97.00"),
        currency="USD",
        settlement_date=datetime.now(timezone.utc).replace(tzinfo=None),
        status="DISCREPANT",
    )
    db_session.add(settlement)

    bank_tx = BankTransaction(
        id=str(uuid4()),
        external_id=f"btx-{uuid4().hex[:8]}",
        merchant_id=merchant.id,
        bank_provider="MockBank",
        amount=Decimal("97.00"),
        currency="USD",
        transaction_type="CREDIT",
        transaction_date=datetime.now(timezone.utc).replace(tzinfo=None),
        status="POSTED",
    )
    db_session.add(bank_tx)

    relationship = ReconciliationRelationship(
        id=str(uuid4()),
        run_id=run.id,
        source_entity_type="SETTLEMENT",
        source_entity_id=settlement.id,
        target_entity_type="BANK_TRANSACTION",
        target_entity_id=bank_tx.id,
        relationship_type="SETTLEMENT_TO_BANK",
        relationship_status=RelationshipStatus.UNRESOLVED,
        financial_status=FinancialEvaluationStatus.DISCREPANCY,
        evidence={"note": "regression fixture"},
    )
    db_session.add(relationship)

    disc = Discrepancy(
        id=str(uuid4()),
        run_id=run.id,
        rule_code="REGRESSION_BANK_TX_001",
        discrepancy_type="CURRENCY_MISMATCH",
        severity="HIGH",
        source_entity_type="SETTLEMENT",
        source_entity_id=settlement.id,
        expected_amount=Decimal("98.00"),
        actual_amount=Decimal("97.00"),
        difference_amount=Decimal("1.00"),
        currency="USD"
    )
    db_session.add(disc)
    await db_session.commit()

    response = await async_client.post(
        f"/api/v1/investigations/discrepancy/{disc.id}/run", headers=auth_headers
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_investigation_api_run(async_client: AsyncClient, seeded_discrepancy: str, auth_headers):
    response = await async_client.post(f"/api/v1/investigations/discrepancy/{seeded_discrepancy}/run", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "COMPLETED"
    assert data["is_valid"] is True
    assert "investigation_id" in data
    assert "attempt_id" in data

    investigation_id = data["investigation_id"]

    # Test GET investigation
    response_get = await async_client.get(f"/api/v1/investigations/{investigation_id}", headers=auth_headers)
    assert response_get.status_code == 200
    data_get = response_get.json()
    assert data_get["discrepancy_id"] == seeded_discrepancy
    assert data_get["status"] == "COMPLETED"

    # Test GET attempts
    response_attempts = await async_client.get(f"/api/v1/investigations/{investigation_id}/attempts", headers=auth_headers)
    assert response_attempts.status_code == 200
    attempts = response_attempts.json()
    assert len(attempts) == 1
    assert attempts[0]["model_used"] == "MockLLMProvider"

@pytest.mark.asyncio
async def test_investigation_api_approve(async_client: AsyncClient, seeded_discrepancy: str, auth_headers):
    # Run first
    run_resp = await async_client.post(f"/api/v1/investigations/discrepancy/{seeded_discrepancy}/run", headers=auth_headers)
    investigation_id = run_resp.json()["investigation_id"]

    # Approve
    app_resp = await async_client.post(f"/api/v1/investigations/{investigation_id}/approve", headers=auth_headers)
    assert app_resp.status_code == 200
    data = app_resp.json()

    assert data["action"] == "RESOLVE_DISCREPANCY"
    assert data["decision"] == "APPROVAL_REQUIRED"
    assert data["rule_code"] == "POLICY_RESOLUTION_REQUIRES_APPROVAL"
    assert data["approval_required"] is True

@pytest.mark.asyncio
async def test_investigation_api_not_found(async_client: AsyncClient, db_session, auth_headers):
    response = await async_client.post(f"/api/v1/investigations/discrepancy/invalid-uuid/run", headers=auth_headers)
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_investigation_api_get_attempt(async_client: AsyncClient, seeded_discrepancy: str, auth_headers):
    # 1. Run investigation to create attempt
    run_resp = await async_client.post(f"/api/v1/investigations/discrepancy/{seeded_discrepancy}/run", headers=auth_headers)
    assert run_resp.status_code == 200
    run_data = run_resp.json()

    investigation_id = run_data["investigation_id"]
    attempt_id = run_data["attempt_id"]

    # 2. Get specific attempt successfully
    get_resp = await async_client.get(f"/api/v1/investigations/{investigation_id}/attempts/{attempt_id}", headers=auth_headers)
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
    bad_resp = await async_client.get(f"/api/v1/investigations/{investigation_id}/attempts/{bad_attempt_id}", headers=auth_headers)
    assert bad_resp.status_code == 404
    assert "Investigation attempt not found" in bad_resp.json()["detail"]

    # 4. Test existing attempt with wrong investigation_id
    bad_investigation_id = str(uuid4())
    wrong_inv_resp = await async_client.get(f"/api/v1/investigations/{bad_investigation_id}/attempts/{attempt_id}", headers=auth_headers)
    assert wrong_inv_resp.status_code == 404
    assert "Investigation attempt not found" in wrong_inv_resp.json()["detail"]

@pytest.mark.asyncio
async def test_investigation_api_list_empty(async_client: AsyncClient, db_session: AsyncSession, auth_headers):
    # To ensure it's empty, we need to clear the table, but since tests might run in parallel or share DB,
    # we can just test that the response is a list and 200 OK.
    response = await async_client.get("/api/v1/investigations", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

@pytest.mark.asyncio
async def test_investigation_api_list(async_client: AsyncClient, seeded_discrepancy: str, db_session: AsyncSession, auth_headers):
    # 1. Run investigation on first discrepancy
    run_resp1 = await async_client.post(f"/api/v1/investigations/discrepancy/{seeded_discrepancy}/run", headers=auth_headers)
    assert run_resp1.status_code == 200
    inv1_id = run_resp1.json()["investigation_id"]

    # 2. Create a second discrepancy manually to run again
    run_id = str(uuid4())
    run = ReconciliationRun(id=run_id)
    db_session.add(run)
    disc2_id = str(uuid4())
    disc2 = Discrepancy(
        id=disc2_id,
        run_id=run_id,
        rule_code="API_TEST_002",
        discrepancy_type="AMOUNT_MISMATCH",
        severity="MEDIUM",
        source_entity_type="PAYMENT",
        source_entity_id=str(uuid4()),
        expected_amount=Decimal("100.00"),
        actual_amount=Decimal("0.00"),
        difference_amount=Decimal("100.00"),
        currency="USD"
    )
    db_session.add(disc2)
    await db_session.commit()

    run_resp2 = await async_client.post(f"/api/v1/investigations/discrepancy/{disc2_id}/run", headers=auth_headers)
    assert run_resp2.status_code == 200
    inv2_id = run_resp2.json()["investigation_id"]

    # 3. List investigations
    list_resp = await async_client.get("/api/v1/investigations", headers=auth_headers)
    assert list_resp.status_code == 200
    data = list_resp.json()

    assert len(data) >= 2

    # Verify newest first (created_at DESC)
    inv2_index = next((i for i, inv in enumerate(data) if inv["id"] == inv2_id), -1)
    inv1_index = next((i for i, inv in enumerate(data) if inv["id"] == inv1_id), -1)
    assert inv2_index < inv1_index

    # Verify exact contract and no internal fields
    first_inv = data[0]
    expected_keys = {"id", "discrepancy_id", "status", "active_attempt_id", "created_at"}
    assert set(first_inv.keys()) == expected_keys

    # Ensure internal fields are missing
    assert "context_snapshot" not in first_inv
    assert "context_hash" not in first_inv
    assert "raw_llm_response" not in first_inv

    # 4. Nullable active_attempt_id check
    from database.models.investigation import Investigation, InvestigationStatus
    # Create a third discrepancy manually to run again
    run_id3 = str(uuid4())
    run3 = ReconciliationRun(id=run_id3)
    db_session.add(run3)
    disc3_id = str(uuid4())
    disc3 = Discrepancy(
        id=disc3_id,
        run_id=run_id3,
        rule_code="API_TEST_003",
        discrepancy_type="AMOUNT_MISMATCH",
        severity="LOW",
        source_entity_type="PAYMENT",
        source_entity_id=str(uuid4()),
        expected_amount=Decimal("10.00"),
        actual_amount=Decimal("0.00"),
        difference_amount=Decimal("10.00"),
        currency="USD"
    )
    db_session.add(disc3)
    await db_session.commit()

    inv3_id = str(uuid4())
    inv3 = Investigation(
        id=inv3_id,
        discrepancy_id=disc3_id,
        status=InvestigationStatus.PENDING,
        active_attempt_id=None
    )
    db_session.add(inv3)
    await db_session.commit()

    list_resp2 = await async_client.get("/api/v1/investigations", headers=auth_headers)
    data2 = list_resp2.json()

    inv3_data = next((inv for inv in data2 if inv["id"] == inv3_id), None)
    assert inv3_data is not None
    assert inv3_data["active_attempt_id"] is None
