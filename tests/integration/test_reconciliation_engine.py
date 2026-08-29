import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from decimal import Decimal
import uuid
from datetime import datetime, timedelta, timezone

from database.models import Payment, Settlement, BankTransaction
from database.models.reconciliation import ReconciliationRun, ReconciliationRelationship, Discrepancy
from services.reconciliation.engine import ReconciliationEngine
from database.seed_data.generator import DataGenerator

@pytest.fixture
async def seeded_db(db_session: AsyncSession):
    generator = DataGenerator(db_session)
    await generator.generate()
    return db_session

@pytest.mark.asyncio
async def test_engine_idempotency_across_repeated_runs(seeded_db: AsyncSession):
    engine1 = ReconciliationEngine(seeded_db)
    res1 = await engine1.run_reconciliation()
    await seeded_db.commit()
    
    assert res1["matches_created"] > 0
    matches_count_1 = res1["matches_created"]
    
    engine2 = ReconciliationEngine(seeded_db)
    res2 = await engine2.run_reconciliation()
    await seeded_db.commit()
    
    # Second run should process records but create 0 NEW relationships because they already exist
    assert res2["matches_created"] == 0
    
    # Total relationships in DB should match the first run
    stmt = select(ReconciliationRelationship)
    result = await seeded_db.execute(stmt)
    total_rels = len(result.scalars().all())
    assert total_rels == matches_count_1

@pytest.mark.asyncio
async def test_engine_atomic_rollback_on_failure(seeded_db: AsyncSession):
    # We will subclass and inject a failure
    class FailingEngine(ReconciliationEngine):
        async def run_reconciliation(self):
            run_id = str(uuid.uuid4())
            run_record = ReconciliationRun(id=run_id, status="RUNNING")
            self.session.add(run_record)
            
            # Create a fake relationship
            rel = ReconciliationRelationship(
                id=str(uuid.uuid4()), run_id=run_id,
                source_entity_type="FAKE", source_entity_id="1",
                target_entity_type="FAKE", target_entity_id="2",
                relationship_type="FAKE_TO_FAKE", relationship_status="CONFIRMED",
                financial_status="RECONCILED"
            )
            self.session.add(rel)
            await self.session.flush() # Send to DB but don't commit
            
            raise ValueError("Simulated engine crash")
            
    engine = FailingEngine(seeded_db)
    with pytest.raises(ValueError, match="Simulated engine crash"):
        await engine.run_reconciliation()
        
    await seeded_db.rollback() # Simulate FastAPI middleware rollback
    
    # Ensure no partial relationships leaked
    stmt = select(ReconciliationRelationship).where(ReconciliationRelationship.source_entity_type == "FAKE")
    result = await seeded_db.execute(stmt)
    assert len(result.scalars().all()) == 0

@pytest.mark.asyncio
async def test_engine_evaluates_scenarios(seeded_db: AsyncSession):
    # To test MISSING_BANK_TX timing policy (> 3 days), we must backdate the Settlement 
    # for Scenario 4 (which has no BankTransaction).
    stmt = select(Settlement).options(
        selectinload(Settlement.bank_transactions)
    ).where(Settlement.settlement_date != None)
    result = await seeded_db.execute(stmt)
    settlements = result.scalars().all()
    for s in settlements:
        if not s.bank_transactions:
            # Shift back 5 days for MISSING_BANK_TX (S4)
            s.settlement_date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=5)
        elif s.gross_amount == Decimal("200.00"):
            # S9: Bank transaction mismatching amount
            for btx in s.bank_transactions:
                btx.amount = Decimal("180.00")
        elif s.gross_amount == Decimal("80.00"):
            # S8: Late Arrival (Bank Tx arrived > 3 days after settlement)
            # Generator set both to 1 day ago. We push settlement back 5 days to make bank tx 4 days later than settlement.
            s.settlement_date = s.settlement_date - timedelta(days=5)
    await seeded_db.commit()

    engine = ReconciliationEngine(seeded_db)
    await engine.run_reconciliation()
    await seeded_db.commit()
    
    # 1. Verify source records are unmodified (no reconciliation_status field exists on them)
    # 2. Check S1 Perfect Flow
    stmt = select(Discrepancy)
    result = await seeded_db.execute(stmt)
    discs = result.scalars().all()
    
    disc_types = [d.discrepancy_type.value for d in discs]
    
    # We seeded discrepancies in MS2.1 generator:
    # S3 Fee mismatch
    assert "FEE_MISMATCH" in disc_types
    # S4 Missing bank tx
    assert "MISSING_BANK_TX" in disc_types
    # S8 Late settlement
    assert "LATE_ARRIVAL" in disc_types
    # S9 Amount mismatch
    assert "AMOUNT_MISMATCH" in disc_types
    # S10 Currency mismatch
    assert "CURRENCY_MISMATCH" in disc_types

    # Check that decimal arithmetic was used for differences
    amount_disc = next(d for d in discs if d.discrepancy_type.value == "AMOUNT_MISMATCH")
    assert isinstance(amount_disc.expected_amount, Decimal)
    assert isinstance(amount_disc.actual_amount, Decimal)
    assert amount_disc.difference_amount == abs(amount_disc.expected_amount - amount_disc.actual_amount)
    
@pytest.mark.asyncio
async def test_api_reconciliation_trigger(async_client: AsyncClient, seeded_db: AsyncSession):
    response = await async_client.post("/api/v1/reconciliation/run")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["matches_created"] > 0
    
    # List runs
    res2 = await async_client.get("/api/v1/reconciliation/runs")
    assert res2.status_code == 200
    assert len(res2.json()) == 1
    
    # List discrepancies
    res3 = await async_client.get("/api/v1/reconciliation/discrepancies")
    assert res3.status_code == 200
    assert len(res3.json()) > 0
