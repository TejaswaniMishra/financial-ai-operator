from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from apps.api.auth import get_current_user
from database.connection import get_async_db
from database.models.reconciliation import ReconciliationRun, Discrepancy
from services.reconciliation.engine import ReconciliationEngine

router = APIRouter(
    prefix="/reconciliation",
    tags=["Reconciliation"],
    dependencies=[Depends(get_current_user)]
)

class ReconciliationResultResponse(BaseModel):
    run_id: str
    status: str
    total_records_processed: int
    matches_created: int
    discrepancies_found: int

class DiscrepancyResponse(BaseModel):
    id: str
    rule_code: str
    discrepancy_type: str
    severity: str
    source_entity_type: str
    source_entity_id: str
    related_entity_type: Optional[str]
    related_entity_id: Optional[str]
    difference_amount: Optional[float]
    currency: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

@router.post("/run", response_model=ReconciliationResultResponse)
async def trigger_reconciliation(
    session: AsyncSession = Depends(get_async_db)
):
    """
    Trigger a deterministic reconciliation engine run synchronously.
    """
    engine = ReconciliationEngine(session)
    result = await engine.run_reconciliation()
    # The transaction commit is handled by the dependency injection `get_async_db` yielding the session.
    # By default, we should commit if we want it to be saved.
    await session.commit()
    return result

@router.get("/runs", response_model=List[ReconciliationResultResponse])
async def list_reconciliation_runs(
    session: AsyncSession = Depends(get_async_db)
):
    stmt = select(ReconciliationRun).order_by(ReconciliationRun.started_at.desc()).limit(100)
    result = await session.execute(stmt)
    runs = result.scalars().all()
    
    return [
        ReconciliationResultResponse(
            run_id=r.id,
            status=r.status.value,
            total_records_processed=r.total_records_processed,
            matches_created=r.matches_created,
            discrepancies_found=r.discrepancies_found
        )
        for r in runs
    ]

@router.get("/discrepancies", response_model=List[DiscrepancyResponse])
async def get_discrepancies(
    session: AsyncSession = Depends(get_async_db)
):
    stmt = select(Discrepancy).order_by(Discrepancy.created_at.desc()).limit(100)
    result = await session.execute(stmt)
    discrepancies = result.scalars().all()
    return discrepancies
