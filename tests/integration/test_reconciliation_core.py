import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from decimal import Decimal
import uuid
from datetime import datetime, timezone

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
async def test_reconciliation_idempotency_behavior(seeded_db: AsyncSession):
    # Run the reconciliation engine multiple times
    engine1 = ReconciliationEngine(seeded_db)
    res1 = await engine1.run_reconciliation()
    await seeded_db.commit()
    
    assert res1["matches_created"] > 0
    matches_count_1 = res1["matches_created"]
    discrepancies_count_1 = res1["discrepancies_found"]
    
    engine2 = ReconciliationEngine(seeded_db)
    res2 = await engine2.run_reconciliation()
    await seeded_db.commit()
    
    # Second run should process records but create 0 NEW relationships
    assert res2["matches_created"] == 0
    assert res2["discrepancies_found"] == 0
    
    # Total relationships in DB should match the first run
    stmt = select(ReconciliationRelationship)
    result = await seeded_db.execute(stmt)
    total_rels = len(result.scalars().all())
    assert total_rels == matches_count_1
    
    stmt_disc = select(Discrepancy)
    result_disc = await seeded_db.execute(stmt_disc)
    total_discs = len(result_disc.scalars().all())
    assert total_discs == discrepancies_count_1

@pytest.mark.asyncio
async def test_reconciliation_atomic_rollback(seeded_db: AsyncSession):
    class FailingEngine(ReconciliationEngine):
        async def run_reconciliation(self):
            run_id = str(uuid.uuid4())
            run_record = ReconciliationRun(id=run_id, status="RUNNING")
            self.session.add(run_record)
            
            rel = ReconciliationRelationship(
                id=str(uuid.uuid4()), run_id=run_id,
                source_entity_type="FAKE", source_entity_id="1",
                target_entity_type="FAKE", target_entity_id="2",
                relationship_type="FAKE_TO_FAKE", relationship_status="CONFIRMED",
                financial_status="RECONCILED"
            )
            self.session.add(rel)
            await self.session.flush() 
            
            raise ValueError("Simulated crash")
            
    engine = FailingEngine(seeded_db)
    with pytest.raises(ValueError, match="Simulated crash"):
        await engine.run_reconciliation()
        
    await seeded_db.rollback() 
    
    stmt = select(ReconciliationRelationship).where(ReconciliationRelationship.source_entity_type == "FAKE")
    result = await seeded_db.execute(stmt)
    assert len(result.scalars().all()) == 0

@pytest.mark.asyncio
async def test_reconciliation_source_immutability(seeded_db: AsyncSession):
    # Capture state before
    stmt_p = select(Payment)
    stmt_s = select(Settlement)
    
    payments_before = (await seeded_db.execute(stmt_p)).scalars().all()
    settlements_before = (await seeded_db.execute(stmt_s)).scalars().all()
    
    state_before = {
        "payments": {p.id: p.updated_at for p in payments_before},
        "settlements": {s.id: s.updated_at for s in settlements_before}
    }
    
    engine = ReconciliationEngine(seeded_db)
    await engine.run_reconciliation()
    await seeded_db.commit()
    
    # Capture state after
    payments_after = (await seeded_db.execute(stmt_p)).scalars().all()
    settlements_after = (await seeded_db.execute(stmt_s)).scalars().all()
    
    state_after = {
        "payments": {p.id: p.updated_at for p in payments_after},
        "settlements": {s.id: s.updated_at for s in settlements_after}
    }
    
    # Assert completely unchanged
    assert state_before == state_after
