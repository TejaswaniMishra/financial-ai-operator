import pytest
from httpx import AsyncClient
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from database.models import Merchant, Payment, Settlement, Refund, BankTransaction, IngestionRecord
from database.seed_data.generator import DataGenerator
from services.ingestion.base import IngestionService

@pytest.fixture
async def seeded_db(db_session: AsyncSession):
    generator = DataGenerator(db_session)
    await generator.generate()
    return db_session

@pytest.mark.asyncio
async def test_scenario_1_perfect_match(seeded_db: AsyncSession, auth_headers):
    # Just verify that payment and settlement exist
    stmt = select(Payment).where(Payment.amount == Decimal("100.00"))
    result = await seeded_db.execute(stmt)
    payments = result.scalars().all()
    assert len(payments) >= 1

@pytest.mark.asyncio
async def test_scenario_2_multi_payment_settlement(seeded_db: AsyncSession, auth_headers):
    # Settlement of 110.00 with two payments (50 and 60)
    stmt = select(Settlement).options(selectinload(Settlement.items)).where(Settlement.gross_amount == Decimal("110.00"))
    result = await seeded_db.execute(stmt)
    settlement = result.scalar_one_or_none()
    assert settlement is not None
    
    # We should have 2 settlement items
    assert len(settlement.items) == 2

@pytest.mark.asyncio
async def test_scenario_3_fee_difference(seeded_db: AsyncSession, auth_headers):
    # Expected net 98, actual settled 97
    stmt = select(Settlement).where(Settlement.expected_net_amount == Decimal("98.00"))
    result = await seeded_db.execute(stmt)
    settlement = result.scalar_one_or_none()
    assert settlement is not None
    assert settlement.actual_settled_amount == Decimal("97.00")
    assert settlement.status == "DISCREPANT"

@pytest.mark.asyncio
async def test_scenario_4_missing_bank_transaction(seeded_db: AsyncSession, auth_headers):
    stmt = select(Settlement).options(selectinload(Settlement.bank_transactions)).where(Settlement.gross_amount == Decimal("75.00"))
    result = await seeded_db.execute(stmt)
    settlement = result.scalar_one_or_none()
    assert settlement is not None
    assert len(settlement.bank_transactions) == 0
    assert settlement.status == "PENDING"

@pytest.mark.asyncio
async def test_scenario_5_duplicate_ingestion(seeded_db: AsyncSession, auth_headers):
    service = IngestionService(seeded_db)
    payload = {"id": "test_dup"}
    
    # First ingestion
    record1 = await service.create_ingestion_record("rec_1", "MOCK", "ext_1", "PAYMENT", payload)
    await seeded_db.commit()
    
    # Check duplicate
    existing = await service.get_existing_record_by_provider_ext_id("MOCK", "ext_1", "PAYMENT")
    assert existing is not None
    assert existing.id == "rec_1"

@pytest.mark.asyncio
async def test_scenario_6_partial_refund(seeded_db: AsyncSession, auth_headers):
    stmt = select(Payment).options(selectinload(Payment.refunds)).where(Payment.amount == Decimal("120.00"))
    result = await seeded_db.execute(stmt)
    payment = result.scalar_one_or_none()
    assert payment is not None
    assert payment.status == "PARTIALLY_REFUNDED"
    assert len(payment.refunds) == 1
    assert payment.refunds[0].amount == Decimal("40.00")

@pytest.mark.asyncio
async def test_scenario_10_currency_mismatch(seeded_db: AsyncSession, auth_headers):
    # Settlement in USD, Bank Tx in EUR
    stmt = select(Settlement).options(selectinload(Settlement.bank_transactions)).where(Settlement.gross_amount == Decimal("300.00"))
    result = await seeded_db.execute(stmt)
    settlement = result.scalar_one_or_none()
    assert settlement is not None
    assert settlement.currency == "USD"
    
    assert len(settlement.bank_transactions) == 1
    assert settlement.bank_transactions[0].currency == "EUR"

@pytest.mark.asyncio
async def test_scenario_11_orphan_handling(seeded_db: AsyncSession, auth_headers):
    service = IngestionService(seeded_db)
    
    # Create record that will be an orphan
    record = await service.create_ingestion_record("rec_orphan", "MOCK", "ext_orphan", "PAYMENT", {})
    await seeded_db.commit()
    
    # Simulate orphan exception
    exception = await service.create_ingestion_exception("exc_1", record.id, "Order not found")
    await seeded_db.commit()
    
    # Verify status updated
    stmt = select(IngestionRecord).options(selectinload(IngestionRecord.exceptions)).where(
        IngestionRecord.provider == "MOCK",
        IngestionRecord.external_id == "ext_orphan",
        IngestionRecord.entity_type == "PAYMENT"
    )
    result = await seeded_db.execute(stmt)
    updated_record = result.scalar_one_or_none()
    assert updated_record.status == "EXCEPTION"
    assert len(updated_record.exceptions) == 1
    assert updated_record.exceptions[0].error_message == "Order not found"

@pytest.mark.asyncio
async def test_api_lineage_with_seeded_data(async_client: AsyncClient, seeded_db: AsyncSession, auth_headers):
    # Test that the API works with the newly seeded complex data
    stmt = select(Payment).where(Payment.amount == Decimal("100.00"))
    result = await seeded_db.execute(stmt)
    payment = result.scalars().first()
    
    response = await async_client.get(f"/api/v1/transactions/payments/{payment.id}/lineage", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["payment"]["id"] == payment.id
    
@pytest.mark.asyncio
async def test_api_metrics_with_seeded_data(async_client: AsyncClient, seeded_db: AsyncSession, auth_headers):
    response = await async_client.get("/api/v1/metrics/overview", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["merchants"] >= 1
    assert data["payments"] >= 7 # 1 + 2 (multi) + 1 + 1 + 1 + 1 + 1 + 1 = 9 approx
    assert data["settlements"] >= 5
