from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from apps.api.auth import get_current_user
from apps.api.authorization import require_permission
from database.connection import get_async_db
from database.models import Merchant, Payment, Settlement, BankTransaction
from packages.rbac.permissions import Permission

router = APIRouter(
    prefix="/metrics",
    tags=["Metrics"],
    dependencies=[Depends(get_current_user)]
)

@router.get("/overview", dependencies=[Depends(require_permission(Permission.VIEW_DASHBOARD))])
async def get_metrics_overview(
    session: AsyncSession = Depends(get_async_db)
):
    """
    Returns aggregate counts and total volume for the dashboard.
    """
    # Total Merchants
    m_stmt = select(func.count(Merchant.id))
    m_count = (await session.execute(m_stmt)).scalar() or 0
    
    # Total Payments
    p_stmt = select(func.count(Payment.id))
    p_count = (await session.execute(p_stmt)).scalar() or 0
    
    # Total Settlements
    s_stmt = select(func.count(Settlement.id))
    s_count = (await session.execute(s_stmt)).scalar() or 0
    
    # Total Bank Transactions
    b_stmt = select(func.count(BankTransaction.id))
    b_count = (await session.execute(b_stmt)).scalar() or 0
    
    # Total Payment Volume (Successful payments)
    pv_stmt = select(func.sum(Payment.amount)).where(Payment.status == "CAPTURED")
    p_volume = (await session.execute(pv_stmt)).scalar() or 0.0
    
    return {
        "merchants": m_count,
        "payments": p_count,
        "settlements": s_count,
        "bank_transactions": b_count,
        "total_volume": float(p_volume)
    }
