"""M13 — Integration tests for the durable ingestion runs API.

Covers the full reliability contract:
- authentication & RBAC (401 / 403 / 200)
- valid materialization into every authoritative domain table
- idempotency (repeated batch + repeated row) with DB-level backstops
- row-level validation (amount / currency / date / enum / references)
- partial failure (COMPLETED_WITH_ERRORS) with per-row counters
- duplicate classification across separate batches
- transactional safety on catastrophic failure (run becomes FAILED, audit
  rows preserved, retry never duplicates)
- genuine concurrent duplicate submission → exactly one financial fact
- lineage (IngestionRecord.run_id) surviving materialization
- downstream Transactions workspace visibility
- security events + notifications emitted from real ingestion events
"""

import asyncio
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.identity import User, UserCredential
from database.models.ingestion import (
    IngestionRecord,
    IngestionRun,
    IngestionRunRecord,
)
from database.models.merchant import Customer, Merchant
from database.models.notification import Notification
from database.models.security import SecurityEvent
from database.models.transaction import (
    BankTransaction,
    Fee,
    Order,
    Payment,
    Refund,
    Settlement,
)
from packages.utils.crypto import hash_password
from packages.utils.id_generator import generate_id
from packages.utils.jwt import create_access_token


# ─── Fixture helpers ────────────────────────────────────────────────────────


@pytest.fixture
async def domain_fixture(db_session: AsyncSession):
    """Seed one merchant + customer + order (idempotent per test DB)."""
    merchant = Merchant(
        id=generate_id("mch"),
        external_id="mch_ext_1",
        name="Test Merchant",
        default_currency="USD",
        timezone="UTC",
        status="ACTIVE",
    )
    db_session.add(merchant)
    await db_session.flush()
    customer = Customer(
        id=generate_id("cus"),
        external_id="cus_ext_1",
        merchant_id=merchant.id,
        display_name="Test Customer",
    )
    db_session.add(customer)
    await db_session.flush()
    order = Order(
        id=generate_id("ord"),
        external_id="ord_ext_1",
        merchant_id=merchant.id,
        customer_id=customer.id,
        amount=Decimal("100.00"),
        currency="USD",
        status="COMPLETED",
    )
    db_session.add(order)
    await db_session.commit()
    return {
        "merchant_id": merchant.id,
        "merchant_external_id": merchant.external_id,
        "order_id": order.id,
        "order_external_id": order.external_id,
    }


@pytest.fixture
async def no_role_headers(db_session):
    """Authenticated user holding NO role (must be denied every permission)."""
    user = User(
        email="norole_ingest@example.com", display_name="No Role User", is_active=True
    )
    db_session.add(user)
    await db_session.flush()
    cred = UserCredential(
        user_id=user.id, password_hash=hash_password("ValidPassword123!")
    )
    db_session.add(cred)
    await db_session.commit()
    token = create_access_token(user_id=user.id)
    return {"Authorization": f"Bearer {token}"}


def _payment_row(domain: dict, ext_id: str = "pay_001", **overrides) -> dict:
    row = {
        "entity_type": "PAYMENT",
        "provider": "MOCK_GATEWAY",
        "external_id": ext_id,
        "merchant_id": domain["merchant_id"],
        "order_id": domain["order_id"],
        "amount": "100.00",
        "currency": "USD",
        "status": "CAPTURED",
        "payment_method_type": "CARD",
        "processed_at": "2026-09-01T10:00:00Z",
    }
    row.update(overrides)
    return row


def _refund_row(domain: dict, ext_id: str = "ref_001", **overrides) -> dict:
    row = {
        "entity_type": "REFUND",
        "provider": "MOCK_GATEWAY",
        "external_id": ext_id,
        "payment_external_id": "pay_001",
        "amount": "10.00",
        "currency": "USD",
        "status": "SUCCEEDED",
        "reason": "customer request",
        "processed_at": "2026-09-02T10:00:00Z",
    }
    row.update(overrides)
    return row


def _settlement_row(domain: dict, ext_id: str = "set_001", **overrides) -> dict:
    row = {
        "entity_type": "SETTLEMENT",
        "provider": "MOCK_GATEWAY",
        "external_id": ext_id,
        "merchant_id": domain["merchant_id"],
        "gross_amount": "1000.00",
        "fee_amount": "30.00",
        "adjustment_amount": "0",
        "expected_net_amount": "970.00",
        "actual_settled_amount": "970.00",
        "currency": "USD",
        "settlement_date": "2026-09-03T00:00:00Z",
        "status": "SETTLED",
    }
    row.update(overrides)
    return row


def _bank_transaction_row(domain: dict, ext_id: str = "btx_001", **overrides) -> dict:
    row = {
        "entity_type": "BANK_TRANSACTION",
        "provider": "MOCK_BANK",
        "external_id": ext_id,
        "merchant_id": domain["merchant_id"],
        "settlement_external_id": "set_001",
        "amount": "970.00",
        "currency": "USD",
        "transaction_type": "CREDIT",
        "transaction_date": "2026-09-04T00:00:00Z",
        "status": "POSTED",
        "description": "payout",
    }
    row.update(overrides)
    return row


async def _count(db: AsyncSession, model, *where) -> int:
    stmt = select(func.count()).select_from(model)
    if where:
        stmt = stmt.where(*where)
    return int((await db.execute(stmt)).scalar_one())


# ─── Auth & RBAC ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ingestion_requires_authentication(async_client: AsyncClient):
    assert (await async_client.post("/api/v1/ingestion/runs", json={})).status_code == 401
    assert (await async_client.get("/api/v1/ingestion/runs")).status_code == 401
    assert (await async_client.get("/api/v1/ingestion/runs/irn_x")).status_code == 401
    assert (await async_client.get("/api/v1/ingestion/runs/irn_x/errors")).status_code == 401
    assert (await async_client.post("/api/v1/ingestion/runs/irn_x/retry")).status_code == 401


@pytest.mark.asyncio
async def test_ingestion_rbac_denied_without_permission(
    async_client: AsyncClient, no_role_headers
):
    """An authenticated user with no DB role cannot read or write ingestion."""
    body = {
        "source_type": "MOCK",
        "source_name": "rbac-denied",
        "records": [{"entity_type": "PAYMENT"}],
    }
    assert (
        await async_client.post("/api/v1/ingestion/runs", json=body, headers=no_role_headers)
    ).status_code == 403
    assert (await async_client.get("/api/v1/ingestion/runs", headers=no_role_headers)).status_code == 403
    assert (
        await async_client.get("/api/v1/ingestion/runs/irn_x/errors", headers=no_role_headers)
    ).status_code == 403


# ─── Valid materialization ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ingest_valid_payment_materializes_domain_fact(
    async_client: AsyncClient,
    db_session: AsyncSession,
    operator_headers,
    domain_fixture,
):
    res = await async_client.post(
        "/api/v1/ingestion/runs",
        json={
            "source_type": "MOCK",
            "source_name": "payments-sep-1",
            "records": [_payment_row(domain_fixture)],
        },
        headers=operator_headers,
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["duplicate"] is False
    run = data["run"]
    assert run["status"] == "COMPLETED"
    assert run["total_records"] == 1
    assert run["successful_records"] == 1

    # Authoritative domain row exists with correct values.
    payment = (
        await db_session.execute(
            select(Payment).where(Payment.external_id == "pay_001")
        )
    ).scalar_one()
    assert payment.merchant_id == domain_fixture["merchant_id"]
    assert payment.order_id == domain_fixture["order_id"]
    assert payment.provider == "MOCK_GATEWAY"
    assert payment.amount == Decimal("100.00")
    assert payment.currency == "USD"
    assert payment.status == "CAPTURED"

    # Lineage survives materialization.
    rec = (
        await db_session.execute(
            select(IngestionRecord).where(
                IngestionRecord.entity_type == "PAYMENT",
                IngestionRecord.external_id == "pay_001",
            )
        )
    ).scalar_one()
    assert rec.run_id == run["id"]
    assert rec.fingerprint
    assert rec.status == "PROCESSED"


# ─── Idempotency ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_duplicate_batch_is_idempotent(
    async_client: AsyncClient,
    db_session: AsyncSession,
    operator_headers,
    domain_fixture,
):
    body = {
        "source_type": "MOCK",
        "source_name": "same-batch",
        "records": [_payment_row(domain_fixture)],
    }
    first = await async_client.post("/api/v1/ingestion/runs", json=body, headers=operator_headers)
    assert first.status_code == 201
    run_id = first.json()["run"]["id"]

    second = await async_client.post("/api/v1/ingestion/runs", json=body, headers=operator_headers)
    assert second.status_code == 201
    second_data = second.json()
    # Identical logical batch → the SAME run, no new facts.
    assert second_data["duplicate"] is True
    assert second_data["run"]["id"] == run_id

    assert await _count(db_session, Payment) == 1
    assert await _count(db_session, IngestionRun) == 1


@pytest.mark.asyncio
async def test_repeated_row_across_batches_is_duplicate_not_new_fact(
    async_client: AsyncClient,
    db_session: AsyncSession,
    operator_headers,
    domain_fixture,
):
    row = _payment_row(domain_fixture)
    body_a = {"source_type": "MOCK", "source_name": "batch-a", "records": [row]}
    body_b = {"source_type": "MOCK", "source_name": "batch-b", "records": [row]}

    res_a = await async_client.post("/api/v1/ingestion/runs", json=body_a, headers=operator_headers)
    assert res_a.json()["run"]["status"] == "COMPLETED"
    assert res_a.json()["run"]["successful_records"] == 1
    run_a_id = res_a.json()["run"]["id"]

    res_b = await async_client.post("/api/v1/ingestion/runs", json=body_b, headers=operator_headers)
    assert res_b.status_code == 201
    b_data = res_b.json()
    # Batch identity is CONTENT-based (source_type + row fingerprints), the
    # source_name is only a label — identical rows in a differently-named
    # batch resolve to the SAME run with duplicate=True, creating no new facts.
    assert b_data["duplicate"] is True
    assert b_data["run"]["id"] == run_a_id

    assert await _count(db_session, Payment) == 1


# ─── Row-level validation ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invalid_amount_float_rejected(
    async_client: AsyncClient,
    db_session: AsyncSession,
    operator_headers,
    domain_fixture,
):
    row = _payment_row(domain_fixture, ext_id="pay_bad", amount=100.00)
    res = await async_client.post(
        "/api/v1/ingestion/runs",
        json={"source_type": "MOCK", "source_name": "bad-amount", "records": [row]},
        headers=operator_headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["run"]["status"] == "COMPLETED_WITH_ERRORS"
    assert data["run"]["rejected_records"] == 1
    assert await _count(db_session, Payment, Payment.external_id == "pay_bad") == 0

    errors = await async_client.get(
        f"/api/v1/ingestion/runs/{data['run']['id']}/errors", headers=operator_headers
    )
    assert errors.status_code == 200
    err = errors.json()["items"][0]
    assert err["status"] == "REJECTED"
    assert err["error_code"] == "INVALID_AMOUNT"
    # Raw payload must never leak through the safe row schema.
    assert "raw_payload" not in err


@pytest.mark.asyncio
async def test_invalid_currency_rejected(
    async_client: AsyncClient,
    db_session: AsyncSession,
    operator_headers,
    domain_fixture,
):
    row = _payment_row(domain_fixture, ext_id="pay_xyz", currency="XYZ")
    res = await async_client.post(
        "/api/v1/ingestion/runs",
        json={"source_type": "MOCK", "source_name": "bad-currency", "records": [row]},
        headers=operator_headers,
    )
    data = res.json()
    assert data["run"]["status"] == "COMPLETED_WITH_ERRORS"
    assert data["run"]["rejected_records"] == 1
    assert await _count(db_session, Payment, Payment.external_id == "pay_xyz") == 0


@pytest.mark.asyncio
async def test_malformed_date_rejected(
    async_client: AsyncClient,
    operator_headers,
    domain_fixture,
):
    row = _payment_row(domain_fixture, ext_id="pay_date", processed_at="not-a-date")
    res = await async_client.post(
        "/api/v1/ingestion/runs",
        json={"source_type": "MOCK", "source_name": "bad-date", "records": [row]},
        headers=operator_headers,
    )
    data = res.json()
    assert data["run"]["rejected_records"] == 1
    errs = (await async_client.get(
        f"/api/v1/ingestion/runs/{data['run']['id']}/errors", headers=operator_headers
    )).json()
    assert errs["items"][0]["error_code"] == "MALFORMED_DATE"


@pytest.mark.asyncio
async def test_missing_required_field_rejected(
    async_client: AsyncClient,
    operator_headers,
    domain_fixture,
):
    row = _payment_row(domain_fixture, ext_id="pay_missing")
    del row["merchant_id"]
    res = await async_client.post(
        "/api/v1/ingestion/runs",
        json={"source_type": "MOCK", "source_name": "missing-field", "records": [row]},
        headers=operator_headers,
    )
    data = res.json()
    assert data["run"]["status"] == "COMPLETED_WITH_ERRORS"
    assert data["run"]["rejected_records"] == 1
    errs = (await async_client.get(
        f"/api/v1/ingestion/runs/{data['run']['id']}/errors", headers=operator_headers
    )).json()
    assert errs["items"][0]["error_code"] == "MISSING_REQUIRED_FIELD"


@pytest.mark.asyncio
async def test_missing_reference_entity_rejected(
    async_client: AsyncClient,
    db_session: AsyncSession,
    operator_headers,
    domain_fixture,
):
    row = _payment_row(domain_fixture, ext_id="pay_ghost", merchant_id="mch_does_not_exist")
    res = await async_client.post(
        "/api/v1/ingestion/runs",
        json={"source_type": "MOCK", "source_name": "ghost-ref", "records": [row]},
        headers=operator_headers,
    )
    data = res.json()
    assert data["run"]["status"] == "COMPLETED_WITH_ERRORS"
    assert data["run"]["rejected_records"] == 1
    errs = (await async_client.get(
        f"/api/v1/ingestion/runs/{data['run']['id']}/errors", headers=operator_headers
    )).json()
    assert errs["items"][0]["error_code"] == "REFERENCED_ENTITY_NOT_FOUND"
    assert await _count(db_session, Payment, Payment.external_id == "pay_ghost") == 0


# ─── Refund domain rules / settlement / bank transaction ────────────────────


@pytest.mark.asyncio
async def test_refund_flow_and_domain_rules(
    async_client: AsyncClient,
    db_session: AsyncSession,
    operator_headers,
    domain_fixture,
):
    pay = await async_client.post(
        "/api/v1/ingestion/runs",
        json={"source_type": "MOCK", "source_name": "pay", "records": [_payment_row(domain_fixture)]},
        headers=operator_headers,
    )
    assert pay.json()["run"]["status"] == "COMPLETED"

    ok_refund = await async_client.post(
        "/api/v1/ingestion/runs",
        json={"source_type": "MOCK", "source_name": "refund-ok", "records": [_refund_row(domain_fixture)]},
        headers=operator_headers,
    )
    data = ok_refund.json()
    assert data["run"]["status"] == "COMPLETED"
    assert data["run"]["successful_records"] == 1
    refund = (await db_session.execute(
        select(Refund).where(Refund.external_id == "ref_001")
    )).scalar_one()
    assert refund.amount == Decimal("10.00")
    assert refund.currency == "USD"

    # Refund exceeding the parent payment → domain rule violation.
    too_big = await async_client.post(
        "/api/v1/ingestion/runs",
        json={
            "source_type": "MOCK",
            "source_name": "refund-too-big",
            "records": [_refund_row(domain_fixture, ext_id="ref_big", amount="500.00")],
        },
        headers=operator_headers,
    )
    too_big_data = too_big.json()
    assert too_big_data["run"]["status"] == "COMPLETED_WITH_ERRORS"
    errs = (await async_client.get(
        f"/api/v1/ingestion/runs/{too_big_data['run']['id']}/errors", headers=operator_headers
    )).json()
    assert errs["items"][0]["error_code"] == "DOMAIN_RULE_VIOLATION"
    assert await _count(db_session, Refund, Refund.external_id == "ref_big") == 0


@pytest.mark.asyncio
async def test_settlement_materializes_and_deduplicates(
    async_client: AsyncClient,
    db_session: AsyncSession,
    operator_headers,
    domain_fixture,
):
    body = {
        "source_type": "MOCK",
        "source_name": "settle",
        "records": [_settlement_row(domain_fixture)],
    }
    res = await async_client.post("/api/v1/ingestion/runs", json=body, headers=operator_headers)
    assert res.json()["run"]["status"] == "COMPLETED"
    settlement = (await db_session.execute(
        select(Settlement).where(Settlement.external_id == "set_001")
    )).scalar_one()
    assert settlement.gross_amount == Decimal("1000.00")
    assert settlement.expected_net_amount == Decimal("970.00")

    res2 = await async_client.post("/api/v1/ingestion/runs", json=body, headers=operator_headers)
    assert res2.json()["duplicate"] is True
    assert await _count(db_session, Settlement) == 1


@pytest.mark.asyncio
async def test_bank_transaction_valid_and_malformed(
    async_client: AsyncClient,
    db_session: AsyncSession,
    operator_headers,
    domain_fixture,
):
    # Valid settlement first (bank tx references it by external id).
    await async_client.post(
        "/api/v1/ingestion/runs",
        json={"source_type": "MOCK", "source_name": "settle", "records": [_settlement_row(domain_fixture)]},
        headers=operator_headers,
    )
    ok = await async_client.post(
        "/api/v1/ingestion/runs",
        json={"source_type": "MOCK", "source_name": "btx", "records": [_bank_transaction_row(domain_fixture)]},
        headers=operator_headers,
    )
    assert ok.json()["run"]["status"] == "COMPLETED"
    btx = (await db_session.execute(
        select(BankTransaction).where(BankTransaction.external_id == "btx_001")
    )).scalar_one()
    assert btx.transaction_type == "CREDIT"
    assert btx.currency == "USD"

    bad = await async_client.post(
        "/api/v1/ingestion/runs",
        json={
            "source_type": "MOCK",
            "source_name": "btx-bad",
            "records": [_bank_transaction_row(domain_fixture, ext_id="btx_bad", transaction_type="WIRE")],
        },
        headers=operator_headers,
    )
    data = bad.json()
    assert data["run"]["status"] == "COMPLETED_WITH_ERRORS"
    errs = (await async_client.get(
        f"/api/v1/ingestion/runs/{data['run']['id']}/errors", headers=operator_headers
    )).json()
    assert errs["items"][0]["error_code"] == "INVALID_STATUS"
    assert await _count(db_session, BankTransaction, BankTransaction.external_id == "btx_bad") == 0


# ─── Partial failure & counters ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mixed_batch_partial_failure_counters(
    async_client: AsyncClient,
    db_session: AsyncSession,
    operator_headers,
    domain_fixture,
):
    # Seed pay_001 first so it becomes a DUPLICATE in the mixed batch.
    await async_client.post(
        "/api/v1/ingestion/runs",
        json={"source_type": "MOCK", "source_name": "seed", "records": [_payment_row(domain_fixture)]},
        headers=operator_headers,
    )
    records = [
        _payment_row(domain_fixture),  # duplicate
        _payment_row(domain_fixture, ext_id="pay_new", amount="42.00"),  # accepted
        _payment_row(domain_fixture, ext_id="pay_bad", currency="EURX"),  # rejected
    ]
    res = await async_client.post(
        "/api/v1/ingestion/runs",
        json={"source_type": "MOCK", "source_name": "mixed", "records": records},
        headers=operator_headers,
    )
    assert res.status_code == 201
    run = res.json()["run"]
    assert run["status"] == "COMPLETED_WITH_ERRORS"
    assert run["total_records"] == 3
    assert run["successful_records"] == 1
    assert run["duplicate_records"] == 1
    assert run["rejected_records"] == 1
    assert run["failed_records"] == 0
    assert run["error_summary"] is not None

    # Valid row persisted, invalid row did not.
    assert await _count(db_session, Payment, Payment.external_id == "pay_new") == 1
    assert await _count(db_session, Payment, Payment.external_id == "pay_bad") == 0


# ─── Transactional safety & retry ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_catastrophic_failure_marks_run_failed_and_retry_is_safe(
    async_client: AsyncClient,
    db_session: AsyncSession,
    operator_headers,
    domain_fixture,
    monkeypatch,
):
    import services.ingestion.batch as batch

    real_materialize = batch.materialize_domain_fact
    _exploded = {"count": 0}

    async def _boom(db, run_id, entity_type, payload, raw, row_fingerprint):
        # Explode only on the FIRST encounter of pay_boom (the initial run);
        # subsequent retries of the same row must materialize normally.
        if raw.get("external_id") == "pay_boom" and _exploded["count"] == 0:
            _exploded["count"] += 1
            raise RuntimeError("simulated catastrophic failure")
        return await real_materialize(db, run_id, entity_type, payload, raw, row_fingerprint)

    monkeypatch.setattr(batch, "materialize_domain_fact", _boom)

    records = [
        _payment_row(domain_fixture, ext_id="pay_ok"),
        _payment_row(domain_fixture, ext_id="pay_boom"),
    ]
    with pytest.raises(RuntimeError):
        # On this ASGI test transport an unhandled route exception escapes
        # (Starlette 1.x behavior). In a real uvicorn server it surfaces as
        # an HTTP 500. Either way, the durable run state is what matters here.
        await async_client.post(
            "/api/v1/ingestion/runs",
            json={"source_type": "MOCK", "source_name": "crash", "records": records},
            headers=operator_headers,
        )

    run_row = (
        await db_session.execute(select(IngestionRun).where(IngestionRun.source_name == "crash"))
    ).scalar_one()
    assert run_row.status == "FAILED"
    assert run_row.failed_records == 1
    # The row that did not crash is preserved (no partial materialization lost).
    assert await _count(db_session, Payment, Payment.external_id == "pay_ok") == 1
    assert await _count(db_session, Payment, Payment.external_id == "pay_boom") == 0

    # Retry: only the FAILED row is reprocessed → accepted, no duplicate.
    retry = await async_client.post(
        f"/api/v1/ingestion/runs/{run_row.id}/retry", headers=operator_headers
    )
    assert retry.status_code == 200, retry.text
    retry_data = retry.json()
    assert retry_data["retried_count"] == 1
    assert retry_data["run"]["status"] == "COMPLETED"
    assert retry_data["run"]["successful_records"] == 1
    assert retry_data["run"]["duplicate_records"] == 0

    assert await _count(db_session, Payment, Payment.external_id == "pay_boom") == 1
    assert await _count(db_session, Payment) == 2  # pay_ok + pay_boom, no duplicates


@pytest.mark.asyncio
async def test_retry_rejects_when_nothing_to_retry(
    async_client: AsyncClient,
    operator_headers,
    domain_fixture,
):
    res = await async_client.post(
        "/api/v1/ingestion/runs",
        json={"source_type": "MOCK", "source_name": "clean", "records": [_payment_row(domain_fixture)]},
        headers=operator_headers,
    )
    run_id = res.json()["run"]["id"]
    retry = await async_client.post(f"/api/v1/ingestion/runs/{run_id}/retry", headers=operator_headers)
    assert retry.status_code == 400
    assert "no failed records" in retry.json()["detail"]


# ─── Concurrency ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_concurrent_identical_batch_produces_single_fact(
    async_client: AsyncClient,
    db_session: AsyncSession,
    operator_headers,
    domain_fixture,
):
    body = {
        "source_type": "MOCK",
        "source_name": "concurrent-race",
        "records": [_payment_row(domain_fixture, ext_id="pay_race")],
    }

    responses = await asyncio.gather(
        *[
            async_client.post("/api/v1/ingestion/runs", json=body, headers=operator_headers)
            for _ in range(8)
        ]
    )
    assert all(r.status_code == 201 for r in responses), [r.status_code for r in responses]

    duplicates = sum(1 for r in responses if r.json()["duplicate"] is True)
    created = sum(1 for r in responses if r.json()["duplicate"] is False)
    # Exactly one submission created the run; all others resolved to it.
    assert created == 1, [r.json()["run"]["id"] for r in responses]
    assert duplicates == 7

    # Exactly one authoritative financial fact + exactly one run.
    assert await _count(db_session, Payment, Payment.external_id == "pay_race") == 1
    assert await _count(db_session, IngestionRun, IngestionRun.source_name == "concurrent-race") == 1


# ─── Lineage, workspace, observability ──────────────────────────────────────


@pytest.mark.asyncio
async def test_lineage_appears_in_transactions_workspace(
    async_client: AsyncClient,
    operator_headers,
    domain_fixture,
):
    res = await async_client.post(
        "/api/v1/ingestion/runs",
        json={"source_type": "MOCK", "source_name": "workspace", "records": [_payment_row(domain_fixture)]},
        headers=operator_headers,
    )
    assert res.json()["run"]["status"] == "COMPLETED"

    ws = await async_client.get("/api/v1/transactions", headers=operator_headers)
    assert ws.status_code == 200
    items = ws.json()["items"]
    assert any(
        item["record_type"] == "PAYMENT" and item["external_id"] == "pay_001"
        for item in items
    )


@pytest.mark.asyncio
async def test_security_events_and_notification_emitted(
    async_client: AsyncClient,
    db_session: AsyncSession,
    operator_headers,
    domain_fixture,
):
    operator_id = (await async_client.get("/api/v1/auth/me", headers=operator_headers)).json()["id"]

    # Successful run → INGESTION_STARTED + INGESTION_COMPLETED (no notification).
    ok = await async_client.post(
        "/api/v1/ingestion/runs",
        json={"source_type": "MOCK", "source_name": "events-ok", "records": [_payment_row(domain_fixture)]},
        headers=operator_headers,
    )
    assert ok.json()["run"]["status"] == "COMPLETED"
    events = (
        await db_session.execute(
            select(SecurityEvent).where(
                SecurityEvent.event_type.in_(["INGESTION_STARTED", "INGESTION_COMPLETED", "INGESTION_FAILED"])
            )
        )
    ).scalars().all()
    types = [e.event_type for e in events]
    assert types.count("INGESTION_STARTED") == 1
    assert types.count("INGESTION_COMPLETED") == 1
    assert "INGESTION_FAILED" not in types
    assert not (await db_session.execute(
        select(Notification).where(
            Notification.user_id == operator_id,
            Notification.type.in_(["INGESTION_COMPLETED_WITH_ERRORS", "INGESTION_FAILED"]),
        )
    )).scalars().all()

    # Run with errors → INGESTION_FAILED event + one notification (not per row).
    bad = await async_client.post(
        "/api/v1/ingestion/runs",
        json={
            "source_type": "MOCK",
            "source_name": "events-bad",
            "records": [_payment_row(domain_fixture, ext_id="pay_ev", currency="BAD")],
        },
        headers=operator_headers,
    )
    assert bad.json()["run"]["status"] == "COMPLETED_WITH_ERRORS"
    events = (
        await db_session.execute(
            select(SecurityEvent).where(SecurityEvent.event_type == "INGESTION_FAILED")
        )
    ).scalars().all()
    assert len(events) == 1
    notes = (
        await db_session.execute(
            select(Notification).where(
                Notification.user_id == operator_id,
                Notification.type == "INGESTION_COMPLETED_WITH_ERRORS",
            )
        )
    ).scalars().all()
    assert len(notes) == 1
    assert notes[0].target_type == "ingestion_run"
    assert notes[0].target_id == bad.json()["run"]["id"]


@pytest.mark.asyncio
async def test_ingestion_run_list_detail_and_errors_endpoints(
    async_client: AsyncClient,
    operator_headers,
    domain_fixture,
):
    await async_client.post(
        "/api/v1/ingestion/runs",
        json={
            "source_type": "MOCK",
            "source_name": "listable",
            "records": [_payment_row(domain_fixture), _payment_row(domain_fixture, ext_id="pay_bad2", amount=1.5)],
        },
        headers=operator_headers,
    )

    listing = await async_client.get("/api/v1/ingestion/runs", headers=operator_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1
    assert "summary" in listing.json()

    run_id = listing.json()["items"][0]["id"]
    detail = await async_client.get(f"/api/v1/ingestion/runs/{run_id}", headers=operator_headers)
    assert detail.status_code == 200
    assert set(detail.json()["record_summary"].keys()) == {"ACCEPTED", "DUPLICATE", "REJECTED", "FAILED"}

    assert (await async_client.get("/api/v1/ingestion/runs/irn_missing", headers=operator_headers)).status_code == 404
    assert (await async_client.get("/api/v1/ingestion/runs/irn_missing/errors", headers=operator_headers)).status_code == 404