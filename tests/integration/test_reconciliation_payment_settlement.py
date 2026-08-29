import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from decimal import Decimal

from database.models import Payment, Settlement, SettlementItem
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
async def test_exact_payment_to_settlement_match(seeded_db: AsyncSession):
    engine = ReconciliationEngine(seeded_db)
    await engine.run_reconciliation()
    await seeded_db.commit()
    
    # Check Scenario 1 (Payment amount == 100.00, Settlement Item amount == 100.00)
    stmt = select(Payment).where(Payment.amount == Decimal("100.00")).limit(1)
    payment = (await seeded_db.execute(stmt)).scalar_one()
    
    stmt = select(ReconciliationRelationship).where(
        ReconciliationRelationship.source_entity_id == payment.id,
        ReconciliationRelationship.relationship_type == "PAYMENT_TO_SETTLEMENT"
    )
    rel = (await seeded_db.execute(stmt)).scalar_one()
    
    assert rel.relationship_status == RelationshipStatus.CONFIRMED
    assert rel.financial_status == FinancialEvaluationStatus.RECONCILED
    assert Decimal(rel.evidence["payment_amount"]) == Decimal("100.00")

@pytest.mark.asyncio
async def test_multi_payment_settlement(seeded_db: AsyncSession):
    engine = ReconciliationEngine(seeded_db)
    await engine.run_reconciliation()
    await seeded_db.commit()
    
    # Check Scenario 2 (Payment 50.00, Payment 60.00 -> Settlement 110.00)
    stmt = select(Payment).where(Payment.amount.in_([Decimal("50.00"), Decimal("60.00")]))
    payments = (await seeded_db.execute(stmt)).scalars().all()
    assert len(payments) == 2
    
    for payment in payments:
        stmt_rel = select(ReconciliationRelationship).where(
            ReconciliationRelationship.source_entity_id == payment.id,
            ReconciliationRelationship.relationship_type == "PAYMENT_TO_SETTLEMENT"
        )
        rel = (await seeded_db.execute(stmt_rel)).scalar_one()
        assert rel.relationship_status == RelationshipStatus.CONFIRMED
        assert rel.financial_status == FinancialEvaluationStatus.RECONCILED

@pytest.mark.asyncio
async def test_relationship_state_vs_financial_state(seeded_db: AsyncSession):
    # We will modify a SettlementItem manually to create an amount mismatch
    stmt = select(Payment).options(
        selectinload(Payment.settlement_items)
    ).where(Payment.amount == Decimal("100.00")).limit(1)
    payment = (await seeded_db.execute(stmt)).scalar_one()
    
    item = payment.settlement_items[0]
    item.amount = Decimal("95.00") # Deliberately mismatch amount
    await seeded_db.commit()
    
    engine = ReconciliationEngine(seeded_db)
    await engine.run_reconciliation()
    await seeded_db.commit()
    
    stmt = select(ReconciliationRelationship).where(
        ReconciliationRelationship.source_entity_id == payment.id,
        ReconciliationRelationship.relationship_type == "PAYMENT_TO_SETTLEMENT"
    )
    rel = (await seeded_db.execute(stmt)).scalar_one()
    
    # Explicit check: Identifier relationship confirmed, but amount mismatch exists
    assert rel.relationship_status == RelationshipStatus.CONFIRMED
    assert rel.financial_status == FinancialEvaluationStatus.DISCREPANCY
    
    # Ensure discrepancy was created
    stmt_disc = select(Discrepancy).where(
        Discrepancy.source_entity_id == payment.id,
        Discrepancy.rule_code == "PAYMENT_SETTLEMENT_AMOUNT_001"
    )
    disc = (await seeded_db.execute(stmt_disc)).scalar_one()
    assert disc.expected_amount == Decimal("100.00")
    assert disc.actual_amount == Decimal("95.00")
    assert disc.difference_amount == Decimal("5.00")
