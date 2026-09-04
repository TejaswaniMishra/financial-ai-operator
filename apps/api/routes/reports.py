"""M12 Reporting API — strictly read-only endpoints.

Every endpoint is:
- Authenticated (get_current_user)
- Permission-protected (VIEW_REPORTS)
- GET-only (no state mutations)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_async_db
from apps.api.auth import get_current_user
from apps.api.authorization import require_permission
from packages.rbac.permissions import Permission

from services.reporting import (
    get_executive_summary,
    get_financial_flow,
    get_reconciliation_analytics,
    get_exception_analytics,
    get_operational_risk,
    get_period_analytics,
    get_trends,
    get_period_comparison,
    get_breakdown,
)
from packages.schemas.reporting import (
    ExecutiveSummary,
    FinancialFlowSummary,
    ReconciliationAnalytics,
    ExceptionAnalytics,
    OperationalRiskSummary,
    PeriodAnalytics,
    TrendResponse,
    PeriodComparisonResponse,
    BreakdownItem,
)

router = APIRouter(
    prefix="/reports",
    tags=["Reports"],
    dependencies=[
        Depends(get_current_user),
        Depends(require_permission(Permission.VIEW_REPORTS)),
    ],
)


@router.get("/summary", response_model=ExecutiveSummary)
async def executive_summary(
    start_date: Optional[datetime] = Query(None, description="UTC start datetime (ISO 8601)"),
    end_date: Optional[datetime] = Query(None, description="UTC end datetime (ISO 8601)"),
    period_id: Optional[str] = Query(None, description="FinancialPeriod ID — overrides start_date/end_date"),
    currency: Optional[str] = Query(None, description="Filter to a single ISO 4217 currency"),
    session: AsyncSession = Depends(get_async_db),
):
    """Executive KPI summary.  All monetary metrics are currency-isolated."""
    return await get_executive_summary(
        session=session,
        start_date=start_date,
        end_date=end_date,
        period_id=period_id,
        currency_filter=currency,
    )


@router.get("/financial-flow", response_model=FinancialFlowSummary)
async def financial_flow(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    period_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_async_db),
):
    """Deterministic pipeline: Payment → Refund / Fee → Settlement → Bank."""
    return await get_financial_flow(
        session=session,
        start_date=start_date,
        end_date=end_date,
        period_id=period_id,
    )


@router.get("/reconciliation", response_model=ReconciliationAnalytics)
async def reconciliation_analytics(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    period_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_async_db),
):
    """Reconciliation metrics using authoritative ReconciliationRelationship data."""
    return await get_reconciliation_analytics(
        session=session,
        start_date=start_date,
        end_date=end_date,
        period_id=period_id,
    )


@router.get("/exceptions", response_model=ExceptionAnalytics)
async def exception_analytics(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    period_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_async_db),
):
    """Exception analytics using the authoritative M10 state derivation."""
    return await get_exception_analytics(
        session=session,
        start_date=start_date,
        end_date=end_date,
        period_id=period_id,
    )


@router.get("/operations", response_model=OperationalRiskSummary)
async def operational_risk(
    session: AsyncSession = Depends(get_async_db),
):
    """Operational risk indicators (counts only — not financial-risk scores)."""
    return await get_operational_risk(session=session)


@router.get("/periods", response_model=PeriodAnalytics)
async def period_analytics(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_async_db),
):
    """Per-period metrics table.  Clicking a period navigates to /periods/{id}."""
    return await get_period_analytics(session=session, limit=limit, offset=offset)


@router.get("/trends", response_model=TrendResponse)
async def trend_analytics(
    metric: str = Query(..., description="One of: payment_count, payment_volume, refund_count, refund_volume, settlement_count, settlement_volume, exception_count"),
    granularity: str = Query("day", description="'day', 'week', or 'month'"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    session: AsyncSession = Depends(get_async_db),
):
    """Time-series aggregation (UTC date buckets)."""
    try:
        return await get_trends(
            session=session,
            metric=metric,
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/comparison", response_model=PeriodComparisonResponse)
async def period_comparison(
    current_start: datetime = Query(...),
    current_end: datetime = Query(...),
    previous_start: datetime = Query(...),
    previous_end: datetime = Query(...),
    session: AsyncSession = Depends(get_async_db),
):
    """Compare two date ranges.  Cross-currency comparisons are never mixed."""
    return await get_period_comparison(
        session=session,
        current_start=current_start,
        current_end=current_end,
        previous_start=previous_start,
        previous_end=previous_end,
    )


@router.get("/breakdowns", response_model=list[BreakdownItem])
async def breakdown_analytics(
    dimension: str = Query(..., description="'provider', 'payment_method', or 'merchant_id'"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    period_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_async_db),
):
    """Breakdown by an authoritative dimension.  Only dimensions backed by the data model are supported."""
    try:
        return await get_breakdown(
            session=session,
            dimension=dimension,
            start_date=start_date,
            end_date=end_date,
            period_id=period_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
