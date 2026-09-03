from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from apps.api.auth import get_current_user
from apps.api.authorization import require_permission
from database.connection import get_async_db
from database.models import Payment
from packages.rbac.permissions import Permission
from packages.schemas.domain import PaymentSchema
from packages.schemas.transactions import (
    TransactionListResponse,
    TransactionDetail,
    TransactionLineageResponse,
    TRANSACTION_TYPES,
)
from services.transactions.workspace import (
    list_transactions,
    get_transaction_detail,
    get_transaction_lineage,
)

router = APIRouter(
    prefix="/transactions",
    tags=["Transactions"],
    dependencies=[Depends(get_current_user)]
)

@router.get("/payments", response_model=list[PaymentSchema], dependencies=[Depends(require_permission(Permission.VIEW_TRANSACTIONS))])
async def list_payments(
    merchant_id: str | None = None,
    session: AsyncSession = Depends(get_async_db)
):
    stmt = select(Payment)
    if merchant_id:
        stmt = stmt.where(Payment.merchant_id == merchant_id)
    result = await session.execute(stmt)
    payments = result.scalars().all()
    return payments

@router.get("/payments/{payment_id}/lineage", dependencies=[Depends(require_permission(Permission.VIEW_TRANSACTIONS))])
async def get_payment_lineage(
    payment_id: str,
    session: AsyncSession = Depends(get_async_db)
):
    """
    Returns the deterministic lineage:
    Order -> Payment -> SettlementItem -> Settlement -> BankTransaction
    """
    stmt = select(Payment).options(
        selectinload(Payment.order),
        selectinload(Payment.refunds),
        selectinload(Payment.fees),
        selectinload(Payment.settlement_items)
    ).where(Payment.id == payment_id)
    
    result = await session.execute(stmt)
    payment = result.scalar_one_or_none()
    
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
        
    # We will fetch related settlement data
    from database.models import SettlementItem, Settlement, BankTransaction
    
    stmt_si = select(SettlementItem).options(
        selectinload(SettlementItem.settlement).selectinload(Settlement.bank_transactions)
    ).where(SettlementItem.payment_id == payment_id)
    
    si_result = await session.execute(stmt_si)
    settlement_items = si_result.scalars().all()
    
    # Construct lineage dict
    lineage = {
        "order": {
            "id": payment.order.id,
            "status": payment.order.status,
            "amount": payment.order.amount,
            "currency": payment.order.currency,
        } if payment.order else None,
        "payment": {
            "id": payment.id,
            "status": payment.status,
            "amount": payment.amount,
            "currency": payment.currency,
            "provider": payment.provider,
        },
        "refunds": [{"id": r.id, "amount": r.amount, "status": r.status} for r in payment.refunds],
        "fees": [{"id": f.id, "amount": f.amount, "fee_type": f.fee_type} for f in payment.fees],
        "settlements": []
    }
    
    for si in settlement_items:
        settle = si.settlement
        settle_data = {
            "settlement_item_id": si.id,
            "settlement_id": settle.id,
            "status": settle.status,
            "gross_amount": settle.gross_amount,
            "expected_net_amount": settle.expected_net_amount,
            "bank_transactions": []
        }
        for btx in settle.bank_transactions:
            settle_data["bank_transactions"].append({
                "id": btx.id,
                "status": btx.status,
                "amount": btx.amount,
                "transaction_type": btx.transaction_type
            })
        lineage["settlements"].append(settle_data)
        
    return lineage


# ─── M9 unified transaction workspace (read-only) ────────────────────────────
# NOTE: registered after /payments* so the static paths win route matching.

@router.get(
    "",
    response_model=TransactionListResponse,
    dependencies=[Depends(require_permission(Permission.VIEW_TRANSACTIONS))],
    summary="List transactions (unified workspace)",
)
async def list_workspace_transactions(
    record_type: str | None = Query(default=None),
    status: str | None = Query(default=None, max_length=64),
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    merchant_id: str | None = Query(default=None, max_length=64),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    min_amount: Decimal | None = Query(default=None),
    max_amount: Decimal | None = Query(default=None),
    reconciled: bool | None = Query(default=None),
    has_discrepancy: bool | None = Query(default=None),
    search: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_async_db),
):
    """
    Deterministic, paginated, read-only workspace over the authoritative
    financial tables. Ordering is `created_at DESC, id DESC`; every filter is
    validated; no ORM objects or sensitive internals are returned.
    """
    if record_type is not None and record_type not in TRANSACTION_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"record_type must be one of: {', '.join(TRANSACTION_TYPES)}",
        )
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must be <= date_to")
    if min_amount is not None and max_amount is not None and min_amount > max_amount:
        raise HTTPException(status_code=422, detail="min_amount must be <= max_amount")

    return await list_transactions(
        session,
        limit=limit,
        offset=offset,
        record_type=record_type,
        status=status,
        currency=currency,
        merchant_id=merchant_id,
        date_from=date_from,
        date_to=date_to,
        min_amount=min_amount,
        max_amount=max_amount,
        reconciled=reconciled,
        has_discrepancy=has_discrepancy,
        search=search,
    )


@router.get(
    "/{transaction_id}",
    response_model=TransactionDetail,
    dependencies=[Depends(require_permission(Permission.VIEW_TRANSACTIONS))],
    summary="Get transaction detail",
)
async def get_workspace_transaction(
    transaction_id: str,
    session: AsyncSession = Depends(get_async_db),
):
    """Authoritative detail for one financial record, including derived
    reconciliation / discrepancy / investigation / action state."""
    detail = await get_transaction_detail(session, transaction_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return detail


@router.get(
    "/{transaction_id}/lineage",
    response_model=TransactionLineageResponse,
    dependencies=[Depends(require_permission(Permission.VIEW_TRANSACTIONS))],
    summary="Get transaction lineage",
)
async def get_workspace_lineage(
    transaction_id: str,
    session: AsyncSession = Depends(get_async_db),
):
    """Lineage with SOURCE financial facts and DERIVED state clearly
    separated. Only relationships established by the backend appear."""
    lineage = await get_transaction_lineage(session, transaction_id)
    if lineage is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return lineage
