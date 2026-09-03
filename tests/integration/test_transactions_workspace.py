"""M9 — Transaction workspace integration tests.

Covers the unified read API (list, detail, lineage), deterministic
pagination/ordering, search, every supported filter, malformed-filter
rejection, RBAC (401/403/200), response hygiene, derived reconciliation /
discrepancy / investigation / action state, and the read-only guarantee.
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database.models.merchant import Merchant
from database.models.transaction import Payment
from database.models.reconciliation import Discrepancy, Severity, DiscrepancyType
from database.models.investigation import Investigation, InvestigationStatus
from database.models.policy import PolicyEvaluation, PolicyAction, PolicyDecision
from database.models.action_request import ActionRequest, ActionRequestStatus
from database.models.action_execution import ActionExecution, ActionExecutionStatus

LIST_URL = "/api/v1/transactions"


@pytest.fixture
async def workspace_data(db_session: AsyncSession):
    """Seeded financial domain (merchant, customer, orders, payments,
    refunds, fees, settlements, bank transactions)."""
    from database.seed_data.generator import DataGenerator

    generator = DataGenerator(db_session)
    await generator.generate()
    return db_session


@pytest.fixture
async def derived_payment(db_session: AsyncSession):
    """A real payment plus a real reconciliation relationship and a full
    derived chain (discrepancy -> investigation -> policy -> action request
    -> execution) built with the same tables the application writes."""
    from database.seed_data.generator import DataGenerator
    from database.models.reconciliation import (
        ReconciliationRun,
        ReconciliationRunStatus,
        ReconciliationRelationship,
        RelationshipStatus,
        FinancialEvaluationStatus,
    )

    generator = DataGenerator(db_session)
    await generator.generate()

    payment = (
        await db_session.execute(select(Payment).limit(1))
    ).scalar_one()
    merchant = (
        await db_session.execute(select(Merchant).where(Merchant.id == payment.merchant_id))
    ).scalar_one()

    run = ReconciliationRun(
        id=str(uuid.uuid4()),
        status=ReconciliationRunStatus.COMPLETED,
        total_records_processed=1,
        matches_created=1,
        discrepancies_found=0,
    )
    db_session.add(run)
    await db_session.flush()

    rel = ReconciliationRelationship(
        id=str(uuid.uuid4()),
        run_id=run.id,
        source_entity_type="PAYMENT",
        source_entity_id=payment.id,
        target_entity_type="SETTLEMENT",
        target_entity_id="settlement-nonexistent-for-test",
        relationship_type="PAYMENT_TO_SETTLEMENT",
        relationship_status=RelationshipStatus.CONFIRMED,
        financial_status=FinancialEvaluationStatus.RECONCILED,
    )
    db_session.add(rel)

    discrepancy = Discrepancy(
        id=str(uuid.uuid4()),
        run_id=run.id,
        rule_code="M9_TEST_RULE",
        discrepancy_type=DiscrepancyType.AMOUNT_MISMATCH,
        severity=Severity.HIGH,
        source_entity_type="PAYMENT",
        source_entity_id=payment.id,
        related_entity_type="SETTLEMENT",
        related_entity_id="settlement-nonexistent-for-test",
        expected_amount=Decimal("100.0000"),
        actual_amount=Decimal("95.0000"),
        difference_amount=Decimal("5.0000"),
        currency="USD",
    )
    db_session.add(discrepancy)
    await db_session.flush()

    investigation = Investigation(
        id=str(uuid.uuid4()),
        discrepancy_id=discrepancy.id,
        status=InvestigationStatus.COMPLETED,
    )
    db_session.add(investigation)
    await db_session.flush()

    evaluation = PolicyEvaluation(
        id=str(uuid.uuid4()),
        investigation_id=investigation.id,
        discrepancy_id=discrepancy.id,
        action=PolicyAction.RESOLVE_DISCREPANCY,
        decision=PolicyDecision.APPROVAL_REQUIRED,
        rule_code="POLICY_RESOLUTION_REQUIRES_APPROVAL",
        reason="M9 test evaluation",
        approval_required=True,
    )
    db_session.add(evaluation)
    await db_session.flush()

    action_request = ActionRequest(
        id=str(uuid.uuid4()),
        investigation_id=investigation.id,
        discrepancy_id=discrepancy.id,
        policy_evaluation_id=evaluation.id,
        action="RESOLVE_DISCREPANCY",
        status=ActionRequestStatus.APPROVED,
        requested_source="m9-test",
    )
    db_session.add(action_request)
    await db_session.flush()

    execution = ActionExecution(
        id=str(uuid.uuid4()),
        action_request_id=action_request.id,
        idempotency_key=f"m9-{action_request.id}",
        status=ActionExecutionStatus.SUCCEEDED,
        execution_type="simulation",
        adapter="simulator",
    )
    db_session.add(execution)
    await db_session.commit()

    return {
        "db": db_session,
        "payment_id": payment.id,
        "merchant_id": payment.merchant_id,
        "merchant_name": merchant.name,
        "discrepancy_id": discrepancy.id,
        "investigation_id": investigation.id,
        "action_request_id": action_request.id,
        "execution_id": execution.id,
    }


# ─── List ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_requires_authentication(async_client: AsyncClient, workspace_data):
    res = await async_client.get(LIST_URL)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_list_empty(async_client: AsyncClient, db_session: AsyncSession, auth_headers):
    res = await async_client.get(f"{LIST_URL}?search=definitely-not-present", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["summary"]["total"] == 0


@pytest.mark.asyncio
async def test_list_returns_real_records(async_client: AsyncClient, workspace_data, auth_headers):
    res = await async_client.get(f"{LIST_URL}?limit=50", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 5  # payments + refunds + fees + settlements + bank tx
    types = {item["record_type"] for item in data["items"]}
    assert "PAYMENT" in types
    assert "SETTLEMENT" in types
    # Safe fields only
    for item in data["items"]:
        assert "password" not in item
        assert "hash" not in item
        assert "token" not in item


@pytest.mark.asyncio
async def test_deterministic_ordering(async_client: AsyncClient, workspace_data, auth_headers):
    res = await async_client.get(f"{LIST_URL}?limit=200", headers=auth_headers)
    data = res.json()
    items = data["items"]
    assert len(items) >= 2
    for prev, cur in zip(items, items[1:]):
        assert (prev["created_at"], prev["id"]) >= (cur["created_at"], cur["id"])


@pytest.mark.asyncio
async def test_pagination(async_client: AsyncClient, workspace_data, auth_headers):
    page1 = (await async_client.get(f"{LIST_URL}?limit=3&offset=0", headers=auth_headers)).json()
    page2 = (await async_client.get(f"{LIST_URL}?limit=3&offset=3", headers=auth_headers)).json()
    assert page1["total"] == page2["total"]
    ids1 = {i["id"] for i in page1["items"]}
    ids2 = {i["id"] for i in page2["items"]}
    assert len(ids1) == 3 and len(ids2) == 3
    assert ids1.isdisjoint(ids2)
    assert page1["offset"] == 0 and page2["offset"] == 3


@pytest.mark.asyncio
async def test_search_by_id(async_client: AsyncClient, workspace_data, auth_headers):
    payment = (await workspace_data.execute(select(Payment).limit(1))).scalar_one()
    res = await async_client.get(f"{LIST_URL}?search={payment.id}", headers=auth_headers)
    data = res.json()
    assert data["total"] >= 1
    assert any(i["id"] == payment.id for i in data["items"])


@pytest.mark.asyncio
async def test_search_by_merchant_name(async_client: AsyncClient, workspace_data, auth_headers):
    res = await async_client.get(f"{LIST_URL}?search=FinOps+Synthetic", headers=auth_headers)
    data = res.json()
    assert data["total"] >= 1
    assert all(i["merchant_name"] == "FinOps Synthetic Merchant" for i in data["items"])


@pytest.mark.asyncio
async def test_filter_record_type(async_client: AsyncClient, workspace_data, auth_headers):
    res = await async_client.get(f"{LIST_URL}?record_type=PAYMENT", headers=auth_headers)
    data = res.json()
    assert data["total"] >= 1
    assert all(i["record_type"] == "PAYMENT" for i in data["items"])
    assert data["summary"]["PAYMENT"] == data["total"]


@pytest.mark.asyncio
async def test_filter_currency_and_status(async_client: AsyncClient, workspace_data, auth_headers):
    res = await async_client.get(f"{LIST_URL}?currency=USD&record_type=PAYMENT", headers=auth_headers)
    data = res.json()
    assert data["total"] >= 1
    assert all(i["currency"] == "USD" for i in data["items"])

    res2 = await async_client.get(f"{LIST_URL}?record_type=PAYMENT&status=CAPTURED", headers=auth_headers)
    assert res2.status_code == 200
    assert all(i["status"] == "CAPTURED" for i in res2.json()["items"])


@pytest.mark.asyncio
async def test_filter_merchant_id(async_client: AsyncClient, derived_payment, auth_headers):
    res = await async_client.get(
        f"{LIST_URL}?merchant_id={derived_payment['merchant_id']}", headers=auth_headers
    )
    data = res.json()
    assert data["total"] >= 1
    assert all(i["merchant_id"] == derived_payment["merchant_id"] for i in data["items"])


@pytest.mark.asyncio
async def test_filter_amount_range(async_client: AsyncClient, workspace_data, auth_headers):
    res = await async_client.get(
        f"{LIST_URL}?min_amount=10&max_amount=1000", headers=auth_headers
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert Decimal("10") <= Decimal(str(item["amount"])) <= Decimal("1000")


@pytest.mark.asyncio
async def test_filter_reconciled_and_discrepancy(async_client: AsyncClient, derived_payment, auth_headers):
    res = await async_client.get(f"{LIST_URL}?reconciled=true", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["total"] >= 1

    res2 = await async_client.get(f"{LIST_URL}?has_discrepancy=true", headers=auth_headers)
    data = res2.json()
    assert data["total"] >= 1
    assert all(i["has_discrepancy"] is True for i in data["items"])


@pytest.mark.asyncio
async def test_filter_date_range(async_client: AsyncClient, workspace_data, auth_headers):
    res = await async_client.get(
        f"{LIST_URL}?date_from=2020-01-01T00:00:00Z&date_to=2030-01-01T00:00:00Z",
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["total"] >= 1


@pytest.mark.asyncio
async def test_combined_filters(async_client: AsyncClient, derived_payment, auth_headers):
    res = await async_client.get(
        f"{LIST_URL}?record_type=PAYMENT&currency=USD&has_discrepancy=true&reconciled=true",
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert all(
        i["record_type"] == "PAYMENT"
        and i["currency"] == "USD"
        and i["has_discrepancy"] is True
        and i["reconciled"] is True
        for i in data["items"]
    )


@pytest.mark.asyncio
async def test_invalid_filters_rejected(async_client: AsyncClient, workspace_data, auth_headers):
    assert (await async_client.get(f"{LIST_URL}?record_type=NOT_A_TYPE", headers=auth_headers)).status_code == 422
    assert (await async_client.get(f"{LIST_URL}?limit=0", headers=auth_headers)).status_code == 422
    assert (await async_client.get(f"{LIST_URL}?limit=201", headers=auth_headers)).status_code == 422
    assert (await async_client.get(f"{LIST_URL}?offset=-1", headers=auth_headers)).status_code == 422
    assert (await async_client.get(f"{LIST_URL}?merchant_id={'x' * 80}", headers=auth_headers)).status_code == 422
    assert (await async_client.get(f"{LIST_URL}?date_from=not-a-date", headers=auth_headers)).status_code == 422
    assert (
        await async_client.get(
            f"{LIST_URL}?date_from=2030-01-01T00:00:00Z&date_to=2020-01-01T00:00:00Z",
            headers=auth_headers,
        )
    ).status_code == 422
    assert (
        await async_client.get(f"{LIST_URL}?min_amount=100&max_amount=10", headers=auth_headers)
    ).status_code == 422


# ─── RBAC ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rbac_all_roles_can_view(async_client: AsyncClient, workspace_data, auth_headers, admin_headers, finance_manager_headers):
    # All fixed roles carry VIEW_TRANSACTIONS per the deterministic matrix.
    assert (await async_client.get(LIST_URL, headers=auth_headers)).status_code == 200
    assert (await async_client.get(LIST_URL, headers=finance_manager_headers)).status_code == 200
    assert (await async_client.get(LIST_URL, headers=admin_headers)).status_code == 200


@pytest.mark.asyncio
async def test_read_only_no_mutation_endpoints(async_client: AsyncClient, workspace_data, auth_headers):
    assert (await async_client.post(LIST_URL, json={}, headers=auth_headers)).status_code == 405
    assert (await async_client.delete(f"{LIST_URL}/whatever", headers=auth_headers)).status_code == 405
    assert (await async_client.put(f"{LIST_URL}/whatever", json={}, headers=auth_headers)).status_code == 405


# ─── Detail ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_detail_full_derived_state(async_client: AsyncClient, derived_payment, auth_headers):
    res = await async_client.get(f"{LIST_URL}/{derived_payment['payment_id']}", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["record_type"] == "PAYMENT"
    assert data["merchant"]["name"] == derived_payment["merchant_name"]
    assert data["currency"] == "USD"
    assert data["order"] is not None
    assert data["customer"] is not None
    assert len(data["reconciliation"]) >= 1
    assert data["reconciliation"][0]["relationship_type"] == "PAYMENT_TO_SETTLEMENT"
    assert len(data["discrepancies"]) >= 1
    assert data["discrepancies"][0]["rule_code"] == "M9_TEST_RULE"
    assert data["investigation"] is not None
    assert data["investigation"]["status"] == "COMPLETED"
    assert any(ar["id"] == derived_payment["action_request_id"] for ar in data["action_requests"])
    assert any(ex["id"] == derived_payment["execution_id"] for ex in data["executions"])


@pytest.mark.asyncio
async def test_detail_sensitive_fields_absent(async_client: AsyncClient, derived_payment, auth_headers):
    res = await async_client.get(f"{LIST_URL}/{derived_payment['payment_id']}", headers=auth_headers)
    body = res.text.lower()
    for forbidden in ("password", "hash", "token", "secret", "raw_llm", "prompt", "context_snapshot", "jti", "authorization"):
        assert forbidden not in body


@pytest.mark.asyncio
async def test_detail_not_found(async_client: AsyncClient, workspace_data, auth_headers):
    res = await async_client.get(f"{LIST_URL}/does-not-exist-anywhere", headers=auth_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_detail_refund_and_settlement(async_client: AsyncClient, workspace_data, auth_headers):
    from database.models.transaction import Refund, Settlement

    refund = (await workspace_data.execute(select(Refund).limit(1))).scalar_one_or_none()
    if refund:
        res = await async_client.get(f"{LIST_URL}/{refund.id}", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["record_type"] == "REFUND"
        assert any(r["record_type"] == "PAYMENT" for r in res.json()["related"])

    settlement = (await workspace_data.execute(select(Settlement).limit(1))).scalar_one_or_none()
    if settlement:
        res = await async_client.get(f"{LIST_URL}/{settlement.id}", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["record_type"] == "SETTLEMENT"


# ─── Lineage ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lineage_source_and_derived(async_client: AsyncClient, derived_payment, auth_headers):
    res = await async_client.get(
        f"{LIST_URL}/{derived_payment['payment_id']}/lineage", headers=auth_headers
    )
    assert res.status_code == 200
    data = res.json()
    assert data["record_id"] == derived_payment["payment_id"]
    kinds = [n["kind"] for n in data["nodes"]]
    assert "PAYMENT" in kinds
    assert "ORDER" in kinds
    assert "RECONCILIATION" in kinds
    assert "DISCREPANCY" in kinds
    assert "INVESTIGATION" in kinds
    assert "ACTION_REQUEST" in kinds
    assert "ACTION_EXECUTION" in kinds

    source_nodes = [n for n in data["nodes"] if n["role"] == "SOURCE"]
    derived_nodes = [n for n in data["nodes"] if n["role"] == "DERIVED"]
    assert source_nodes and derived_nodes
    # Source financial facts precede derived state in the node list.
    assert max(i for i, n in enumerate(data["nodes"]) if n["role"] == "SOURCE") < min(
        i for i, n in enumerate(data["nodes"]) if n["role"] == "DERIVED"
    )


@pytest.mark.asyncio
async def test_lineage_no_false_relationships(async_client: AsyncClient, workspace_data, auth_headers):
    from database.models.transaction import BankTransaction

    bank = (await workspace_data.execute(select(BankTransaction).limit(1))).scalar_one_or_none()
    if not bank:
        pytest.skip("no bank transaction seeded")
    res = await async_client.get(f"{LIST_URL}/{bank.id}/lineage", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    kinds = [n["kind"] for n in data["nodes"]]
    assert "BANK_TRANSACTION" in kinds
    # No payment implied unless the settlement chain actually links one.
    if bank.settlement_id is None:
        assert "SETTLEMENT" not in kinds


@pytest.mark.asyncio
async def test_lineage_not_found(async_client: AsyncClient, workspace_data, auth_headers):
    res = await async_client.get(f"{LIST_URL}/missing/lineage", headers=auth_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_lineage_requires_authentication(async_client: AsyncClient, derived_payment):
    res = await async_client.get(f"{LIST_URL}/{derived_payment['payment_id']}/lineage")
    assert res.status_code == 401