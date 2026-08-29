import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from decimal import Decimal
from datetime import datetime, timezone, timedelta

from database.models import Settlement, BankTransaction
from database.models.reconciliation import ReconciliationRelationship, Discrepancy
from services.reconciliation.engine import ReconciliationEngine
from database.seed_data.generator import DataGenerator
from packages.schemas.reconciliation import RelationshipStatus, FinancialEvaluationStatus

@pytest.fixture
async def seeded_db(db_session: AsyncSession):
    generator = DataGenerator(db_session)
    await generator.generate()
    return db_session

@pytest.mark.asyncio
async def test_fee_adjusted_reconciliation(seeded_db: AsyncSession):
    engine = ReconciliationEngine(seeded_db)
    await engine.run_reconciliation()
    await seeded_db.commit()
    
    # S3 Fee Difference
    stmt = select(Settlement).where(Settlement.gross_amount == Decimal("100.00"), Settlement.fee_amount == Decimal("2.00")).limit(1)
    s = (await seeded_db.execute(stmt)).scalar_one()
    
    stmt = select(Discrepancy).where(
        Discrepancy.source_entity_id == s.id,
        Discrepancy.discrepancy_type == "FEE_MISMATCH"
    )
    disc = (await seeded_db.execute(stmt)).scalar_one()
    
    # gross 100 - fee 2 = expected 98. actual settled was 97
    assert disc.expected_amount == Decimal("98.00")
    assert disc.actual_amount == Decimal("97.00")
    assert disc.difference_amount == Decimal("1.00")

@pytest.mark.asyncio
async def test_missing_bank_transaction(seeded_db: AsyncSession):
    # Setup S4 correctly (shift back 5 days to trigger > 3 days logic)
    stmt = select(Settlement).options(selectinload(Settlement.bank_transactions)).where(Settlement.gross_amount == Decimal("75.00"))
    s = (await seeded_db.execute(stmt)).scalar_one()
    s.settlement_date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=5)
    await seeded_db.commit()
    
    engine = ReconciliationEngine(seeded_db)
    await engine.run_reconciliation()
    await seeded_db.commit()
    
    # Verify no relationship created because missing
    stmt = select(ReconciliationRelationship).where(
        ReconciliationRelationship.source_entity_id == s.id,
        ReconciliationRelationship.relationship_type == "SETTLEMENT_TO_BANK"
    )
    rel = (await seeded_db.execute(stmt)).scalar_one_or_none()
    assert rel is None # UNRESOLVED is not tracked, or could be if we designed it that way
    
    stmt = select(Discrepancy).where(Discrepancy.source_entity_id == s.id, Discrepancy.discrepancy_type == "MISSING_BANK_TX")
    disc = (await seeded_db.execute(stmt)).scalar_one()
    assert disc.expected_amount == Decimal("73.50")
    assert disc.actual_amount is None

@pytest.mark.asyncio
async def test_candidate_window_vs_timing_policy(seeded_db: AsyncSession):
    # S8 Late Arrival
    stmt = select(Settlement).where(Settlement.gross_amount == Decimal("80.00"))
    s = (await seeded_db.execute(stmt)).scalar_one()
    s.settlement_date = s.settlement_date - timedelta(days=5) # Bank tx is now 4 days later than settlement
    await seeded_db.commit()
    
    engine = ReconciliationEngine(seeded_db)
    await engine.run_reconciliation()
    await seeded_db.commit()
    
    # Ensure it was found within the candidate window and classified as LATE_ARRIVAL
    stmt = select(ReconciliationRelationship).where(
        ReconciliationRelationship.source_entity_id == s.id,
        ReconciliationRelationship.relationship_type == "SETTLEMENT_TO_BANK"
    )
    rel = (await seeded_db.execute(stmt)).scalar_one()
    assert rel.relationship_status == RelationshipStatus.CONFIRMED
    assert rel.financial_status == FinancialEvaluationStatus.DISCREPANCY
    
    stmt = select(Discrepancy).where(Discrepancy.source_entity_id == s.id, Discrepancy.discrepancy_type == "LATE_ARRIVAL")
    disc = (await seeded_db.execute(stmt)).scalar_one()
    assert disc.rule_code == "SETTLEMENT_TIMING_001"

@pytest.mark.asyncio
async def test_bank_amount_mismatch(seeded_db: AsyncSession):
    # S9
    stmt = select(Settlement).options(selectinload(Settlement.bank_transactions)).where(Settlement.gross_amount == Decimal("200.00"))
    s = (await seeded_db.execute(stmt)).scalar_one()
    s.bank_transactions[0].amount = Decimal("180.00") # Force mismatch
    await seeded_db.commit()
    
    engine = ReconciliationEngine(seeded_db)
    await engine.run_reconciliation()
    await seeded_db.commit()
    
    stmt = select(Discrepancy).where(Discrepancy.source_entity_id == s.id, Discrepancy.discrepancy_type == "AMOUNT_MISMATCH")
    disc = (await seeded_db.execute(stmt)).scalar_one()
    assert disc.expected_amount == Decimal("190.00")
    assert disc.actual_amount == Decimal("180.00")
    assert disc.difference_amount == Decimal("10.00")

@pytest.mark.asyncio
async def test_currency_mismatch(seeded_db: AsyncSession):
    engine = ReconciliationEngine(seeded_db)
    await engine.run_reconciliation()
    await seeded_db.commit()
    
    # S10
    stmt = select(Settlement).where(Settlement.gross_amount == Decimal("300.00"))
    s = (await seeded_db.execute(stmt)).scalar_one()
    
    stmt = select(Discrepancy).where(Discrepancy.source_entity_id == s.id, Discrepancy.discrepancy_type == "CURRENCY_MISMATCH")
    disc = (await seeded_db.execute(stmt)).scalar_one()
    assert disc.currency == "USD"
