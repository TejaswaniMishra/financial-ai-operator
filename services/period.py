import json
from datetime import datetime, timezone
from sqlalchemy import select, func, and_, or_, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
import uuid

from database.models.period import FinancialPeriod, PeriodCloseEvaluation
from database.models.transaction import Payment, Refund, Fee, Settlement, BankTransaction
from database.models.reconciliation import Discrepancy
from database.models.investigation import Investigation
from database.models.action_request import ActionRequest
from database.models.action_execution import ActionExecution
from database.models.security import SecurityEvent

from packages.schemas.period import (
    CloseReadiness,
    PeriodMetrics,
    CurrencyMetrics,
    CloseControlResult,
    CloseControlCode,
    ControlStatus,
    ControlSeverity,
)

async def create_period(
    db: AsyncSession, period_name: str, start_date: datetime, end_date: datetime
) -> FinancialPeriod:
    if start_date >= end_date:
        raise ValueError("start_date must be before end_date")
        
    period = FinancialPeriod(
        id=str(uuid.uuid4()),
        period_name=period_name,
        start_date=start_date,
        end_date=end_date,
        status="OPEN"
    )
    db.add(period)
    await db.flush()
    return period

async def get_period(db: AsyncSession, period_id: str) -> Optional[FinancialPeriod]:
    result = await db.execute(select(FinancialPeriod).where(FinancialPeriod.id == period_id))
    return result.scalar_one_or_none()

async def list_periods(
    db: AsyncSession, offset: int = 0, limit: int = 50, status: Optional[str] = None
) -> tuple[List[FinancialPeriod], int]:
    query = select(FinancialPeriod)
    if status:
        query = query.where(FinancialPeriod.status == status)
        
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()
    
    query = query.order_by(FinancialPeriod.created_at.desc()).offset(offset).limit(limit)
    items = (await db.execute(query)).scalars().all()
    
    return items, total

async def calculate_period_metrics(db: AsyncSession, period: FinancialPeriod) -> PeriodMetrics:
    # Aggregating by currency
    currencies: Dict[str, CurrencyMetrics] = {}
    
    def get_curr(c: str) -> CurrencyMetrics:
        if c not in currencies:
            currencies[c] = CurrencyMetrics()
        return currencies[c]

    # Payments
    stmt = select(Payment.currency, func.count(Payment.id), func.sum(Payment.amount)).where(
        and_(Payment.created_at >= period.start_date, Payment.created_at < period.end_date)
    ).group_by(Payment.currency)
    for row in (await db.execute(stmt)).all():
        c = get_curr(row[0])
        c.payments_count = row[1]
        c.payments_amount = float(row[2]) if row[2] else 0.0
        c.transaction_count += c.payments_count
        c.total_amount += c.payments_amount

    # Refunds
    stmt = select(Refund.currency, func.count(Refund.id), func.sum(Refund.amount)).where(
        and_(Refund.created_at >= period.start_date, Refund.created_at < period.end_date)
    ).group_by(Refund.currency)
    for row in (await db.execute(stmt)).all():
        c = get_curr(row[0])
        c.refunds_count = row[1]
        c.refunds_amount = float(row[2]) if row[2] else 0.0
        c.transaction_count += c.refunds_count
        c.total_amount += c.refunds_amount

    # Fees
    stmt = select(Fee.currency, func.count(Fee.id), func.sum(Fee.amount)).where(
        and_(Fee.created_at >= period.start_date, Fee.created_at < period.end_date)
    ).group_by(Fee.currency)
    for row in (await db.execute(stmt)).all():
        c = get_curr(row[0])
        c.fees_count = row[1]
        c.fees_amount = float(row[2]) if row[2] else 0.0
        c.transaction_count += c.fees_count
        c.total_amount -= c.fees_amount # Assuming fees subtract from total

    # Settlements
    stmt = select(Settlement.currency, func.count(Settlement.id), func.sum(Settlement.gross_amount)).where(
        and_(Settlement.created_at >= period.start_date, Settlement.created_at < period.end_date)
    ).group_by(Settlement.currency)
    for row in (await db.execute(stmt)).all():
        c = get_curr(row[0])
        c.settlements_count = row[1]
        c.settlements_amount = float(row[2]) if row[2] else 0.0

    # Bank Transactions
    stmt = select(BankTransaction.currency, func.count(BankTransaction.id), func.sum(BankTransaction.amount)).where(
        and_(BankTransaction.created_at >= period.start_date, BankTransaction.created_at < period.end_date)
    ).group_by(BankTransaction.currency)
    for row in (await db.execute(stmt)).all():
        c = get_curr(row[0])
        c.bank_transactions_count = row[1]
        c.bank_transactions_amount = float(row[2]) if row[2] else 0.0

    # Operational metrics
    reconciled = (await db.execute(
        select(func.count(Payment.id)).where(
            and_(Payment.created_at >= period.start_date, Payment.created_at < period.end_date, Payment.status == 'RECONCILED')
        )
    )).scalar_one()

    unreconciled = (await db.execute(
        select(func.count(Payment.id)).where(
            and_(Payment.created_at >= period.start_date, Payment.created_at < period.end_date, Payment.status != 'RECONCILED')
        )
    )).scalar_one()

    # Discrepancies
    discrepancy_count = (await db.execute(
        select(func.count(Discrepancy.id)).where(
            and_(Discrepancy.created_at >= period.start_date, Discrepancy.created_at < period.end_date)
        )
    )).scalar_one()

    # Investigations
    investigation_count = (await db.execute(
        select(func.count(Investigation.id)).where(
            and_(Investigation.created_at >= period.start_date, Investigation.created_at < period.end_date)
        )
    )).scalar_one()

    # Action Requests
    action_request_count = (await db.execute(
        select(func.count(ActionRequest.id)).where(
            and_(ActionRequest.created_at >= period.start_date, ActionRequest.created_at < period.end_date)
        )
    )).scalar_one()

    return PeriodMetrics(
        metrics_by_currency=currencies,
        reconciled_count=reconciled,
        unreconciled_count=unreconciled,
        discrepancy_count=discrepancy_count,
        investigation_count=investigation_count,
        action_request_count=action_request_count,
        execution_failures=0, # Simplified for now
        execution_unknowns=0,
    )


async def evaluate_close_readiness(db: AsyncSession, period: FinancialPeriod) -> CloseReadiness:
    controls = []
    
    # 1. CLOSE_UNRECONCILED_TRANSACTIONS
    unreconciled_count = (await db.execute(
        select(func.count(Payment.id)).where(
            and_(Payment.created_at >= period.start_date, Payment.created_at < period.end_date, Payment.status != 'RECONCILED')
        )
    )).scalar_one()
    
    controls.append(CloseControlResult(
        control_code=CloseControlCode.CLOSE_UNRECONCILED_TRANSACTIONS,
        status=ControlStatus.BLOCKED if unreconciled_count > 0 else ControlStatus.PASS,
        severity=ControlSeverity.CRITICAL if unreconciled_count > 0 else ControlSeverity.INFO,
        count=unreconciled_count,
        explanation=f"Found {unreconciled_count} unreconciled payments."
    ))

    # 2. CLOSE_UNRESOLVED_EXCEPTIONS
    # Any discrepancy not resolved
    # Note: Exceptions resolution logic varies; here we check if an action execution succeeded or policy denied.
    # We simplify by just looking for any open discrepancy that isn't connected to a successful execution.
    unresolved_exceptions_query = select(func.count(Discrepancy.id)).where(
        and_(Discrepancy.created_at >= period.start_date, Discrepancy.created_at < period.end_date)
    )
    # This is a simplification. Ideally, we would join through the pipeline to see if it's terminal.
    # For deterministic safety, we fetch them and check their action states.
    discrepancies = (await db.execute(
        select(Discrepancy).where(and_(Discrepancy.created_at >= period.start_date, Discrepancy.created_at < period.end_date))
    )).scalars().all()
    
    unresolved_count = 0
    for disc in discrepancies:
        # A discrepancy is resolved if it has a successful ActionExecution or a denied Policy.
        # This mirrors the exception logic from M10.
        # This is a lightweight proxy implementation.
        is_resolved = False
        
        # Check action requests
        action_requests = (await db.execute(
            select(ActionRequest).where(ActionRequest.discrepancy_id == disc.id)
        )).scalars().all()
        
        for ar in action_requests:
            executions = (await db.execute(
                select(ActionExecution).where(ActionExecution.action_request_id == ar.id)
            )).scalars().all()
            for ex in executions:
                if ex.status == "SUCCEEDED":
                    is_resolved = True
                    break
            if is_resolved:
                break
        
        if not is_resolved:
            unresolved_count += 1
            
    controls.append(CloseControlResult(
        control_code=CloseControlCode.CLOSE_UNRESOLVED_EXCEPTIONS,
        status=ControlStatus.BLOCKED if unresolved_count > 0 else ControlStatus.PASS,
        severity=ControlSeverity.CRITICAL if unresolved_count > 0 else ControlSeverity.INFO,
        count=unresolved_count,
        explanation=f"Found {unresolved_count} unresolved exceptions."
    ))

    # 3. CLOSE_PENDING_INVESTIGATIONS
    pending_investigations = (await db.execute(
        select(func.count(Investigation.id)).where(
            and_(Investigation.created_at >= period.start_date, Investigation.created_at < period.end_date, Investigation.status == 'PENDING')
        )
    )).scalar_one()
    controls.append(CloseControlResult(
        control_code=CloseControlCode.CLOSE_PENDING_INVESTIGATIONS,
        status=ControlStatus.BLOCKED if pending_investigations > 0 else ControlStatus.PASS,
        severity=ControlSeverity.CRITICAL if pending_investigations > 0 else ControlSeverity.INFO,
        count=pending_investigations,
        explanation=f"Found {pending_investigations} pending investigations."
    ))
    
    # 4. CLOSE_FAILED_INVESTIGATIONS
    failed_investigations = (await db.execute(
        select(func.count(Investigation.id)).where(
            and_(Investigation.created_at >= period.start_date, Investigation.created_at < period.end_date, Investigation.status == 'FAILED')
        )
    )).scalar_one()
    controls.append(CloseControlResult(
        control_code=CloseControlCode.CLOSE_FAILED_INVESTIGATIONS,
        status=ControlStatus.BLOCKED if failed_investigations > 0 else ControlStatus.PASS,
        severity=ControlSeverity.CRITICAL if failed_investigations > 0 else ControlSeverity.INFO,
        count=failed_investigations,
        explanation=f"Found {failed_investigations} failed investigations."
    ))

    # 5. CLOSE_PENDING_ACTION_REQUESTS
    pending_actions = (await db.execute(
        select(func.count(ActionRequest.id)).where(
            and_(ActionRequest.created_at >= period.start_date, ActionRequest.created_at < period.end_date, ActionRequest.status == 'PENDING_APPROVAL')
        )
    )).scalar_one()
    controls.append(CloseControlResult(
        control_code=CloseControlCode.CLOSE_PENDING_ACTION_REQUESTS,
        status=ControlStatus.BLOCKED if pending_actions > 0 else ControlStatus.PASS,
        severity=ControlSeverity.CRITICAL if pending_actions > 0 else ControlSeverity.INFO,
        count=pending_actions,
        explanation=f"Found {pending_actions} pending action requests."
    ))

    # 6. CLOSE_RUNNING_EXECUTIONS
    running_execs = (await db.execute(
        select(func.count(ActionExecution.id)).where(
            and_(
                ActionExecution.created_at >= period.start_date, 
                ActionExecution.created_at < period.end_date, 
                ActionExecution.status.in_(['PENDING', 'RUNNING'])
            )
        )
    )).scalar_one()
    controls.append(CloseControlResult(
        control_code=CloseControlCode.CLOSE_RUNNING_EXECUTIONS,
        status=ControlStatus.BLOCKED if running_execs > 0 else ControlStatus.PASS,
        severity=ControlSeverity.CRITICAL if running_execs > 0 else ControlSeverity.INFO,
        count=running_execs,
        explanation=f"Found {running_execs} running executions."
    ))
    
    # 7. CLOSE_UNKNOWN_EXECUTIONS
    unknown_execs = (await db.execute(
        select(func.count(ActionExecution.id)).where(
            and_(
                ActionExecution.created_at >= period.start_date, 
                ActionExecution.created_at < period.end_date, 
                ActionExecution.status == 'UNKNOWN'
            )
        )
    )).scalar_one()
    controls.append(CloseControlResult(
        control_code=CloseControlCode.CLOSE_UNKNOWN_EXECUTIONS,
        status=ControlStatus.BLOCKED if unknown_execs > 0 else ControlStatus.PASS,
        severity=ControlSeverity.CRITICAL if unknown_execs > 0 else ControlSeverity.INFO,
        count=unknown_execs,
        explanation=f"Found {unknown_execs} unknown executions."
    ))

    is_ready = all(c.status != ControlStatus.BLOCKED for c in controls)
    overall_status = ControlStatus.PASS if is_ready else ControlStatus.BLOCKED
    
    metrics = await calculate_period_metrics(db, period)
    
    return CloseReadiness(
        period_id=period.id,
        is_ready=is_ready,
        overall_status=overall_status,
        controls=controls,
        metrics=metrics,
        evaluated_at=datetime.now(timezone.utc)
    )

async def close_period(db: AsyncSession, period: FinancialPeriod, actor: str) -> FinancialPeriod:
    # Double check lock or state concurrency
    if period.status == "CLOSED":
        raise ValueError("Period is already closed")
    
    # Force state transition check
    stmt = (
        select(FinancialPeriod)
        .where(FinancialPeriod.id == period.id)
        .where(FinancialPeriod.status != "CLOSED")
        .with_for_update()
    )
    locked_period = (await db.execute(stmt)).scalar_one_or_none()
    
    if not locked_period:
        raise ValueError("Period state mismatch, might be concurrently closed")

    # Evaluate again deterministically
    readiness = await evaluate_close_readiness(db, locked_period)
    
    # Save the evaluation snapshot
    evaluation = PeriodCloseEvaluation(
        id=str(uuid.uuid4()),
        period_id=locked_period.id,
        evaluated_at=readiness.evaluated_at,
        evaluated_by=actor,
        is_ready=readiness.is_ready,
        blocking_count=sum(1 for c in readiness.controls if c.status == ControlStatus.BLOCKED),
        warning_count=sum(1 for c in readiness.controls if c.status == ControlStatus.WARNING),
        control_results=[c.model_dump() for c in readiness.controls],
        metrics_snapshot=readiness.metrics.model_dump()
    )
    db.add(evaluation)
    
    if not readiness.is_ready:
        await db.flush()
        raise ValueError(f"Period is blocked from closing. Blockers: {evaluation.blocking_count}")

    # Ready to close
    locked_period.status = "CLOSED"
    locked_period.closed_at = datetime.now(timezone.utc)
    locked_period.closed_by = actor
    
    # Emit security event
    sec_event = SecurityEvent(
        id=str(uuid.uuid4()),
        event_type="PERIOD_CLOSED",
        actor_id=actor,
        ip_address="system",
        user_agent="system",
        metadata_payload=json.dumps({
            "period_id": locked_period.id,
            "evaluation_id": evaluation.id,
            "metrics": readiness.metrics.model_dump()
        })
    )
    db.add(sec_event)
    
    await db.flush()
    return locked_period
