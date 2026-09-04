from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from database.dependencies import get_db_session
from database.models.identity import User
from apps.api.dependencies import get_current_user, require_permission
from packages.rbac.permissions import Permission
from packages.schemas.period import (
    PeriodResponse,
    PeriodListResponse,
    PeriodCreate,
    PeriodDetailResponse,
    CloseReadiness,
    PeriodCloseEvaluationResponse
)
from database.models.period import FinancialPeriod, PeriodCloseEvaluation
from services.period import (
    create_period,
    list_periods,
    get_period,
    evaluate_close_readiness,
    close_period,
    calculate_period_metrics
)

router = APIRouter(prefix="/periods", tags=["periods"])

@router.post("", response_model=PeriodResponse)
async def api_create_period(
    payload: PeriodCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_permission(Permission.CREATE_PERIOD))
):
    try:
        period = await create_period(
            db=db,
            period_name=payload.period_name,
            start_date=payload.start_date,
            end_date=payload.end_date
        )
        return period
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("", response_model=PeriodListResponse)
async def api_list_periods(
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_permission(Permission.VIEW_PERIODS))
):
    items, total = await list_periods(db, offset=offset, limit=limit, status=status)
    return {
        "items": items,
        "total": total,
        "page": (offset // limit) + 1 if limit > 0 else 1,
        "size": limit
    }

@router.get("/{period_id}", response_model=PeriodDetailResponse)
async def api_get_period(
    period_id: str,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_permission(Permission.VIEW_PERIODS))
):
    period = await get_period(db, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")
        
    readiness = await evaluate_close_readiness(db, period)
    
    # Get latest evaluation if exists
    from sqlalchemy import select
    latest_eval = (await db.execute(
        select(PeriodCloseEvaluation)
        .where(PeriodCloseEvaluation.period_id == period.id)
        .order_by(PeriodCloseEvaluation.evaluated_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    
    return {
        "period": period,
        "metrics": readiness.metrics,
        "readiness": readiness,
        "latest_evaluation": latest_eval
    }

@router.get("/{period_id}/controls", response_model=CloseReadiness)
async def api_get_period_controls(
    period_id: str,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_permission(Permission.VIEW_PERIODS))
):
    period = await get_period(db, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")
    
    return await evaluate_close_readiness(db, period)

@router.post("/{period_id}/evaluate", response_model=CloseReadiness)
async def api_evaluate_period_close(
    period_id: str,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_permission(Permission.EVALUATE_PERIOD_CLOSE))
):
    period = await get_period(db, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")
    
    return await evaluate_close_readiness(db, period)

@router.post("/{period_id}/close", response_model=PeriodResponse)
async def api_close_period(
    period_id: str,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(require_permission(Permission.CLOSE_PERIOD))
):
    period = await get_period(db, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")
        
    if period.status == "CLOSED":
        raise HTTPException(status_code=409, detail="Period is already closed")
    
    # Authorize human close.
    # We require CLOSE_PERIOD, but for M11 prompt compliance, let's also enforce it here
    
    try:
        closed_period = await close_period(db, period, actor=user.email)
        return closed_period
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
