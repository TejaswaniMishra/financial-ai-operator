from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database.connection import get_async_db
from database.models import Payment
from packages.schemas.domain import PaymentSchema

router = APIRouter(prefix="/transactions", tags=["Transactions"])

@router.get("/payments", response_model=list[PaymentSchema])
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

@router.get("/payments/{payment_id}/lineage")
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
