"""M12 Reporting Service.

IMPORTANT: This service is STRICTLY READ-ONLY.
No financial state is mutated here. No reconciliation, investigation,
policy evaluation, action request, execution, period evaluation or close
is triggered by any function in this module.

All metrics originate from authoritative database tables.
Currencies are NEVER aggregated across ISO codes.
Double-counting is explicitly guarded against for 1:N joins (see notes).
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, case, select, text, distinct, and_, or_, cast, Date, String
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.transaction import Payment, Refund, Fee, Settlement, SettlementItem, BankTransaction
from database.models.reconciliation import ReconciliationRelationship, Discrepancy
from database.models.investigation import Investigation, InvestigationAttempt
from database.models.action_request import ActionRequest
from database.models.action_execution import ActionExecution
from database.models.period import FinancialPeriod, PeriodCloseEvaluation
from packages.schemas.reconciliation import FinancialEvaluationStatus
from packages.schemas.exceptions import OverallExceptionState
from packages.schemas.reporting import (
    ExecutiveSummary,
    AmountByCurrency,
    FinancialFlowStage,
    FinancialFlowSummary,
    ReconciliationAnalytics,
    ExceptionStateCount,
    ExceptionTypeCount,
    RootCauseCount,
    ExceptionAnalytics,
    OperationalRiskSummary,
    PeriodReportRow,
    PeriodAnalytics,
    TrendPoint,
    TrendResponse,
    ComparisonRow,
    PeriodComparisonResponse,
    BreakdownItem,
)


# ─── Internal helpers ─────────────────────────────────────────────────────────

async def _resolve_period_dates(
    session: AsyncSession,
    period_id: Optional[str],
    start_date: Optional[datetime],
    end_date: Optional[datetime],
) -> tuple[Optional[datetime], Optional[datetime]]:
    """If period_id given, return the period's exact start/end dates.
    Otherwise fall back to caller-supplied dates.
    Never mix period dates with explicit date overrides.
    """
    if period_id:
        stmt = select(FinancialPeriod).where(FinancialPeriod.id == period_id)
        result = await session.execute(stmt)
        period = result.scalar_one_or_none()
        if period:
            return period.start_date, period.end_date
    return start_date, end_date


def _payment_date_filter(start: Optional[datetime], end: Optional[datetime]):
    """SQLAlchemy filter clauses for Payment date range."""
    clauses = []
    if start:
        clauses.append(Payment.processed_at >= start)
    if end:
        clauses.append(Payment.processed_at <= end)
    return clauses


def _amounts_by_currency(rows) -> list[AmountByCurrency]:
    """Convert (currency, count, total) aggregate rows to schema objects."""
    result = []
    for row in rows:
        result.append(AmountByCurrency(
            currency=row.currency or "UNKNOWN",
            count=int(row.cnt),
            total_amount=Decimal(str(row.total or 0)).quantize(Decimal("0.0001")),
        ))
    return result


# ─── EXECUTIVE SUMMARY ────────────────────────────────────────────────────────

async def get_executive_summary(
    session: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    period_id: Optional[str] = None,
    currency_filter: Optional[str] = None,
) -> ExecutiveSummary:
    """Aggregate KPI metrics.

    Double-counting guard:
      Payments are queried directly from the payments table — NOT via
      settlement_items.  SettlementItem is a 1:N join from Payment; joining
      and then SUM(payment.amount) would multiply payment amounts.
    """
    start, end = await _resolve_period_dates(session, period_id, start_date, end_date)

    # ── Payment volume (direct from payments; never via settlement_items) ──
    pay_q = select(
        Payment.currency,
        func.count(distinct(Payment.id)).label("cnt"),
        func.sum(Payment.amount).label("total"),
    ).group_by(Payment.currency)
    if start:
        pay_q = pay_q.where(Payment.processed_at >= start)
    if end:
        pay_q = pay_q.where(Payment.processed_at <= end)
    if currency_filter:
        pay_q = pay_q.where(Payment.currency == currency_filter)
    pay_rows = (await session.execute(pay_q)).all()

    # ── Refund volume ──
    ref_q = select(
        Refund.currency,
        func.count(distinct(Refund.id)).label("cnt"),
        func.sum(Refund.amount).label("total"),
    ).group_by(Refund.currency)
    if start:
        ref_q = ref_q.where(Refund.processed_at >= start)
    if end:
        ref_q = ref_q.where(Refund.processed_at <= end)
    if currency_filter:
        ref_q = ref_q.where(Refund.currency == currency_filter)
    ref_rows = (await session.execute(ref_q)).all()

    # ── Fee volume ──
    fee_q = select(
        Fee.currency,
        func.count(distinct(Fee.id)).label("cnt"),
        func.sum(Fee.amount).label("total"),
    ).group_by(Fee.currency)
    # Fees don't have processed_at; link via payment
    if start or end:
        fee_payment_ids = select(Payment.id)
        if start:
            fee_payment_ids = fee_payment_ids.where(Payment.processed_at >= start)
        if end:
            fee_payment_ids = fee_payment_ids.where(Payment.processed_at <= end)
        fee_q = fee_q.where(
            or_(
                Fee.payment_id.in_(fee_payment_ids),
                # Fees linked directly to settlement without payment: include via settlement date
                and_(
                    Fee.payment_id.is_(None),
                    Fee.settlement_id.in_(
                        select(Settlement.id).where(
                            *([Settlement.settlement_date >= start] if start else []),
                            *([Settlement.settlement_date <= end] if end else []),
                        )
                    )
                )
            )
        )
    if currency_filter:
        fee_q = fee_q.where(Fee.currency == currency_filter)
    fee_rows = (await session.execute(fee_q)).all()

    # ── Settlement volume (direct from settlements) ──
    set_q = select(
        Settlement.currency,
        func.count(distinct(Settlement.id)).label("cnt"),
        func.sum(Settlement.gross_amount).label("total"),
    ).group_by(Settlement.currency)
    if start:
        set_q = set_q.where(Settlement.settlement_date >= start)
    if end:
        set_q = set_q.where(Settlement.settlement_date <= end)
    if currency_filter:
        set_q = set_q.where(Settlement.currency == currency_filter)
    set_rows = (await session.execute(set_q)).all()

    # ── Bank Transaction volume ──
    btx_q = select(
        BankTransaction.currency,
        func.count(distinct(BankTransaction.id)).label("cnt"),
        func.sum(BankTransaction.amount).label("total"),
    ).group_by(BankTransaction.currency)
    if start:
        btx_q = btx_q.where(BankTransaction.transaction_date >= start)
    if end:
        btx_q = btx_q.where(BankTransaction.transaction_date <= end)
    if currency_filter:
        btx_q = btx_q.where(BankTransaction.currency == currency_filter)
    btx_rows = (await session.execute(btx_q)).all()

    # ── Reconciliation counts (from ReconciliationRelationship, source=PAYMENT) ──
    # "Reconciled" means financial_status = RECONCILED
    recon_q = select(
        ReconciliationRelationship.financial_status,
        func.count(distinct(ReconciliationRelationship.id)).label("cnt"),
    ).where(
        ReconciliationRelationship.source_entity_type == "PAYMENT"
    ).group_by(ReconciliationRelationship.financial_status)
    recon_rows = (await session.execute(recon_q)).all()
    reconciled_cnt = 0
    unreconciled_cnt = 0
    for rr in recon_rows:
        val = rr.financial_status.value if hasattr(rr.financial_status, "value") else str(rr.financial_status)
        if val == FinancialEvaluationStatus.RECONCILED.value:
            reconciled_cnt += int(rr.cnt)
        else:
            unreconciled_cnt += int(rr.cnt)

    # ── Discrepancy count ──
    disc_q = select(func.count(distinct(Discrepancy.id)))
    disc_cnt = (await session.execute(disc_q)).scalar() or 0

    # ── Unresolved exception count (OPEN or INVESTIGATING or AWAITING_APPROVAL or APPROVED or EXECUTING or FAILED or UNKNOWN) ──
    # Reusing the _determine_overall_state logic via the same SQL CASE as exceptions service
    exec_status = ActionExecution.status
    req_status = ActionRequest.status
    pol_decision_col = None  # lazy-import to avoid circular
    from database.models.policy import PolicyEvaluation
    pol_decision_col = PolicyEvaluation.decision
    inv_status = Investigation.status

    overall_state_expr = case(
        (exec_status == "SUCCEEDED", OverallExceptionState.RESOLVED.value),
        (exec_status == "FAILED", OverallExceptionState.FAILED.value),
        (exec_status == "UNKNOWN", OverallExceptionState.UNKNOWN.value),
        (exec_status.in_(["PENDING", "RUNNING"]), OverallExceptionState.EXECUTING.value),
        (req_status == "APPROVED", OverallExceptionState.APPROVED.value),
        (req_status == "PENDING_APPROVAL", OverallExceptionState.AWAITING_APPROVAL.value),
        (req_status.in_(["REJECTED", "CANCELLED"]), OverallExceptionState.OPEN.value),
        (pol_decision_col == "DENIED", OverallExceptionState.RESOLVED.value),
        (pol_decision_col == "APPROVAL_REQUIRED", OverallExceptionState.AWAITING_APPROVAL.value),
        (inv_status == "PENDING", OverallExceptionState.INVESTIGATING.value),
        (inv_status.in_(["FAILED", "UNAVAILABLE"]), OverallExceptionState.FAILED.value),
        else_=OverallExceptionState.OPEN.value,
    )

    unresolved_states = [
        OverallExceptionState.OPEN.value,
        OverallExceptionState.INVESTIGATING.value,
        OverallExceptionState.AWAITING_APPROVAL.value,
        OverallExceptionState.APPROVED.value,
        OverallExceptionState.EXECUTING.value,
        OverallExceptionState.FAILED.value,
        OverallExceptionState.UNKNOWN.value,
    ]

    unresolved_subq = (
        select(func.count(distinct(Discrepancy.id)))
        .select_from(Discrepancy)
        .outerjoin(Investigation, Investigation.discrepancy_id == Discrepancy.id)
        .outerjoin(PolicyEvaluation, PolicyEvaluation.investigation_id == Investigation.id)
        .outerjoin(ActionRequest, ActionRequest.policy_evaluation_id == PolicyEvaluation.id)
        .outerjoin(ActionExecution, ActionExecution.action_request_id == ActionRequest.id)
        .where(overall_state_expr.in_(unresolved_states))
    )
    unresolved_exc = (await session.execute(unresolved_subq)).scalar() or 0

    inv_cnt = (await session.execute(select(func.count(distinct(Investigation.id))))).scalar() or 0
    pending_req = (await session.execute(
        select(func.count(distinct(ActionRequest.id))).where(ActionRequest.status == "PENDING_APPROVAL")
    )).scalar() or 0
    failed_exec = (await session.execute(
        select(func.count(distinct(ActionExecution.id))).where(ActionExecution.status == "FAILED")
    )).scalar() or 0
    unknown_exec = (await session.execute(
        select(func.count(distinct(ActionExecution.id))).where(ActionExecution.status == "UNKNOWN")
    )).scalar() or 0

    return ExecutiveSummary(
        period_start=start,
        period_end=end,
        period_id=period_id,
        payment_volume=_amounts_by_currency(pay_rows),
        refund_volume=_amounts_by_currency(ref_rows),
        fee_volume=_amounts_by_currency(fee_rows),
        settlement_volume=_amounts_by_currency(set_rows),
        bank_transaction_volume=_amounts_by_currency(btx_rows),
        total_payment_count=sum(int(r.cnt) for r in pay_rows),
        total_refund_count=sum(int(r.cnt) for r in ref_rows),
        total_fee_count=sum(int(r.cnt) for r in fee_rows),
        total_settlement_count=sum(int(r.cnt) for r in set_rows),
        total_bank_transaction_count=sum(int(r.cnt) for r in btx_rows),
        reconciled_count=reconciled_cnt,
        unreconciled_count=unreconciled_cnt,
        discrepancy_count=int(disc_cnt),
        unresolved_exception_count=int(unresolved_exc),
        investigation_count=int(inv_cnt),
        pending_action_request_count=int(pending_req),
        failed_execution_count=int(failed_exec),
        unknown_execution_count=int(unknown_exec),
    )


# ─── FINANCIAL FLOW ───────────────────────────────────────────────────────────

async def get_financial_flow(
    session: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    period_id: Optional[str] = None,
) -> FinancialFlowSummary:
    """Deterministic pipeline view.

    Each stage is queried independently from its own canonical table.
    One-to-many joins are never used when computing SUM amounts.
    """
    start, end = await _resolve_period_dates(session, period_id, start_date, end_date)
    stages: list[FinancialFlowStage] = []

    async def _stage(model, date_col, amount_col, label: str):
        q = select(
            model.currency,
            func.count(distinct(model.id)).label("cnt"),
            func.sum(amount_col).label("total"),
        ).group_by(model.currency)
        if start:
            q = q.where(date_col >= start)
        if end:
            q = q.where(date_col <= end)
        rows = (await session.execute(q)).all()
        for row in rows:
            stages.append(FinancialFlowStage(
                stage=label,
                currency=row.currency or "UNKNOWN",
                count=int(row.cnt),
                total_amount=Decimal(str(row.total or 0)).quantize(Decimal("0.0001")),
            ))

    await _stage(Payment, Payment.processed_at, Payment.amount, "PAYMENT")
    await _stage(Refund, Refund.processed_at, Refund.amount, "REFUND")
    await _stage(Settlement, Settlement.settlement_date, Settlement.gross_amount, "SETTLEMENT")
    await _stage(BankTransaction, BankTransaction.transaction_date, BankTransaction.amount, "BANK_TRANSACTION")

    # Fees: no direct date column; link through payment or settlement dates
    fee_q = select(
        Fee.currency,
        func.count(distinct(Fee.id)).label("cnt"),
        func.sum(Fee.amount).label("total"),
    ).group_by(Fee.currency)
    fee_rows = (await session.execute(fee_q)).all()
    for row in fee_rows:
        stages.append(FinancialFlowStage(
            stage="FEE",
            currency=row.currency or "UNKNOWN",
            count=int(row.cnt),
            total_amount=Decimal(str(row.total or 0)).quantize(Decimal("0.0001")),
        ))

    return FinancialFlowSummary(period_start=start, period_end=end, stages=stages)


# ─── RECONCILIATION ANALYTICS ─────────────────────────────────────────────────

async def get_reconciliation_analytics(
    session: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    period_id: Optional[str] = None,
) -> ReconciliationAnalytics:
    start, end = await _resolve_period_dates(session, period_id, start_date, end_date)

    # Total eligible Payments in window
    pay_count_q = select(func.count(distinct(Payment.id)))
    if start:
        pay_count_q = pay_count_q.where(Payment.processed_at >= start)
    if end:
        pay_count_q = pay_count_q.where(Payment.processed_at <= end)
    total_payments = (await session.execute(pay_count_q)).scalar() or 0

    # ReconciliationRelationship counts by financial_status for PAYMENT sources
    rr_q = select(
        ReconciliationRelationship.financial_status,
        func.count(distinct(ReconciliationRelationship.id)).label("cnt"),
    ).where(
        ReconciliationRelationship.source_entity_type == "PAYMENT"
    ).group_by(ReconciliationRelationship.financial_status)
    rr_rows = (await session.execute(rr_q)).all()

    reconciled = 0
    disc_rr = 0
    unresolved_rr = 0
    for row in rr_rows:
        val = row.financial_status.value if hasattr(row.financial_status, "value") else str(row.financial_status)
        if val == FinancialEvaluationStatus.RECONCILED.value:
            reconciled += int(row.cnt)
        elif val == FinancialEvaluationStatus.DISCREPANCY.value:
            disc_rr += int(row.cnt)
        else:
            unresolved_rr += int(row.cnt)

    # Unreconciled = payments with no reconciled relationship
    # This uses EXISTS so no double-counting
    reconciled_payment_ids = (
        select(ReconciliationRelationship.source_entity_id)
        .where(
            ReconciliationRelationship.source_entity_type == "PAYMENT",
            ReconciliationRelationship.financial_status == FinancialEvaluationStatus.RECONCILED,
        )
    )
    unreconciled_q = select(func.count(distinct(Payment.id))).where(
        Payment.id.not_in(reconciled_payment_ids)
    )
    if start:
        unreconciled_q = unreconciled_q.where(Payment.processed_at >= start)
    if end:
        unreconciled_q = unreconciled_q.where(Payment.processed_at <= end)
    unreconciled_count = (await session.execute(unreconciled_q)).scalar() or 0

    rate = (reconciled / total_payments) if total_payments > 0 else None

    # Discrepancy counts & amounts
    disc_count_q = select(func.count(distinct(Discrepancy.id)))
    disc_count = (await session.execute(disc_count_q)).scalar() or 0

    disc_amt_q = select(
        Discrepancy.currency,
        func.count(distinct(Discrepancy.id)).label("cnt"),
        func.sum(func.abs(Discrepancy.difference_amount)).label("total"),
    ).where(Discrepancy.difference_amount.isnot(None)).group_by(Discrepancy.currency)
    disc_amt_rows = (await session.execute(disc_amt_q)).all()

    return ReconciliationAnalytics(
        period_start=start,
        period_end=end,
        total_payments_eligible=int(total_payments),
        reconciled_count=reconciled,
        unreconciled_count=int(unreconciled_count),
        reconciliation_rate=round(rate, 4) if rate is not None else None,
        discrepancy_count=int(disc_count),
        discrepancy_amount_by_currency=_amounts_by_currency(disc_amt_rows),
        relationship_reconciled=reconciled,
        relationship_discrepancy=disc_rr,
        relationship_unresolved=unresolved_rr,
    )


# ─── EXCEPTION ANALYTICS ──────────────────────────────────────────────────────

async def get_exception_analytics(
    session: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    period_id: Optional[str] = None,
) -> ExceptionAnalytics:
    start, end = await _resolve_period_dates(session, period_id, start_date, end_date)

    from database.models.policy import PolicyEvaluation

    # Build the same CASE expression used in services/exceptions.py
    exec_status = ActionExecution.status
    req_status = ActionRequest.status
    pol_dec = PolicyEvaluation.decision
    inv_status = Investigation.status

    state_expr = case(
        (exec_status == "SUCCEEDED", OverallExceptionState.RESOLVED.value),
        (exec_status == "FAILED", OverallExceptionState.FAILED.value),
        (exec_status == "UNKNOWN", OverallExceptionState.UNKNOWN.value),
        (exec_status.in_(["PENDING", "RUNNING"]), OverallExceptionState.EXECUTING.value),
        (req_status == "APPROVED", OverallExceptionState.APPROVED.value),
        (req_status == "PENDING_APPROVAL", OverallExceptionState.AWAITING_APPROVAL.value),
        (req_status.in_(["REJECTED", "CANCELLED"]), OverallExceptionState.OPEN.value),
        (pol_dec == "DENIED", OverallExceptionState.RESOLVED.value),
        (pol_dec == "APPROVAL_REQUIRED", OverallExceptionState.AWAITING_APPROVAL.value),
        (inv_status == "PENDING", OverallExceptionState.INVESTIGATING.value),
        (inv_status.in_(["FAILED", "UNAVAILABLE"]), OverallExceptionState.FAILED.value),
        else_=OverallExceptionState.OPEN.value,
    ).label("computed_state")

    base_q = (
        select(Discrepancy, state_expr)
        .outerjoin(Investigation, Investigation.discrepancy_id == Discrepancy.id)
        .outerjoin(PolicyEvaluation, PolicyEvaluation.investigation_id == Investigation.id)
        .outerjoin(ActionRequest, ActionRequest.policy_evaluation_id == PolicyEvaluation.id)
        .outerjoin(ActionExecution, ActionExecution.action_request_id == ActionRequest.id)
    )

    # Wrap as subquery to group by computed state
    sub = base_q.subquery()
    by_state_q = select(sub.c.computed_state, func.count().label("cnt")).group_by(sub.c.computed_state)
    state_rows = (await session.execute(by_state_q)).all()

    by_type_q = select(
        Discrepancy.discrepancy_type,
        func.count(distinct(Discrepancy.id)).label("cnt"),
    ).group_by(Discrepancy.discrepancy_type)
    type_rows = (await session.execute(by_type_q)).all()

    # Root causes from InvestigationAttempt.validated_output
    # We query root_cause from validated_output JSON where is_valid=True
    # SQLite: json_extract; Postgres: ->> operator; using SQLAlchemy text for compatibility
    # We'll use Python-side aggregation to stay DB-agnostic
    attempt_q = select(InvestigationAttempt.validated_output).where(InvestigationAttempt.is_valid == True)
    attempt_rows = (await session.execute(attempt_q)).scalars().all()
    root_cause_counts: dict[str, int] = {}
    for vo in attempt_rows:
        if isinstance(vo, dict):
            rc = vo.get("root_cause")
            if rc:
                root_cause_counts[str(rc)] = root_cause_counts.get(str(rc), 0) + 1

    # Unresolved amounts by currency
    unresolved_states_vals = [
        OverallExceptionState.OPEN.value,
        OverallExceptionState.INVESTIGATING.value,
        OverallExceptionState.AWAITING_APPROVAL.value,
        OverallExceptionState.APPROVED.value,
        OverallExceptionState.EXECUTING.value,
        OverallExceptionState.FAILED.value,
        OverallExceptionState.UNKNOWN.value,
    ]
    unresolved_sub = (
        select(Discrepancy)
        .outerjoin(Investigation, Investigation.discrepancy_id == Discrepancy.id)
        .outerjoin(PolicyEvaluation, PolicyEvaluation.investigation_id == Investigation.id)
        .outerjoin(ActionRequest, ActionRequest.policy_evaluation_id == PolicyEvaluation.id)
        .outerjoin(ActionExecution, ActionExecution.action_request_id == ActionRequest.id)
        .where(state_expr.in_(unresolved_states_vals))
    ).subquery()
    unresolved_amt_q = select(
        unresolved_sub.c.currency,
        func.count(distinct(unresolved_sub.c.id)).label("cnt"),
        func.sum(func.abs(unresolved_sub.c.difference_amount)).label("total"),
    ).where(unresolved_sub.c.difference_amount.isnot(None)).group_by(unresolved_sub.c.currency)
    unresolved_amt_rows = (await session.execute(unresolved_amt_q)).all()

    total_exc = sum(int(r.cnt) for r in state_rows)

    return ExceptionAnalytics(
        period_start=start,
        period_end=end,
        total_exceptions=total_exc,
        by_state=[ExceptionStateCount(state=r.computed_state, count=int(r.cnt)) for r in state_rows],
        by_type=[ExceptionTypeCount(
            type=r.discrepancy_type.value if hasattr(r.discrepancy_type, "value") else str(r.discrepancy_type),
            count=int(r.cnt),
        ) for r in type_rows],
        by_root_cause=[RootCauseCount(root_cause=k, count=v) for k, v in sorted(root_cause_counts.items(), key=lambda x: -x[1])],
        unresolved_amount_by_currency=_amounts_by_currency(unresolved_amt_rows),
    )


# ─── OPERATIONAL RISK ─────────────────────────────────────────────────────────

async def get_operational_risk(session: AsyncSession) -> OperationalRiskSummary:
    """Operational health indicators.

    These are COUNTS only — never converted to financial amounts or
    arbitrary composite risk scores.
    """
    from database.models.policy import PolicyEvaluation

    state_expr = case(
        (ActionExecution.status == "SUCCEEDED", OverallExceptionState.RESOLVED.value),
        (ActionExecution.status == "FAILED", OverallExceptionState.FAILED.value),
        (ActionExecution.status == "UNKNOWN", OverallExceptionState.UNKNOWN.value),
        (ActionExecution.status.in_(["PENDING", "RUNNING"]), OverallExceptionState.EXECUTING.value),
        (ActionRequest.status == "APPROVED", OverallExceptionState.APPROVED.value),
        (ActionRequest.status == "PENDING_APPROVAL", OverallExceptionState.AWAITING_APPROVAL.value),
        (ActionRequest.status.in_(["REJECTED", "CANCELLED"]), OverallExceptionState.OPEN.value),
        (PolicyEvaluation.decision == "DENIED", OverallExceptionState.RESOLVED.value),
        (PolicyEvaluation.decision == "APPROVAL_REQUIRED", OverallExceptionState.AWAITING_APPROVAL.value),
        (Investigation.status == "PENDING", OverallExceptionState.INVESTIGATING.value),
        (Investigation.status.in_(["FAILED", "UNAVAILABLE"]), OverallExceptionState.FAILED.value),
        else_=OverallExceptionState.OPEN.value,
    )

    unresolved_states = [
        OverallExceptionState.OPEN.value,
        OverallExceptionState.INVESTIGATING.value,
        OverallExceptionState.AWAITING_APPROVAL.value,
        OverallExceptionState.APPROVED.value,
        OverallExceptionState.EXECUTING.value,
        OverallExceptionState.FAILED.value,
        OverallExceptionState.UNKNOWN.value,
    ]

    unresolved_exc = (await session.execute(
        select(func.count(distinct(Discrepancy.id)))
        .select_from(Discrepancy)
        .outerjoin(Investigation, Investigation.discrepancy_id == Discrepancy.id)
        .outerjoin(PolicyEvaluation, PolicyEvaluation.investigation_id == Investigation.id)
        .outerjoin(ActionRequest, ActionRequest.policy_evaluation_id == PolicyEvaluation.id)
        .outerjoin(ActionExecution, ActionExecution.action_request_id == ActionRequest.id)
        .where(state_expr.in_(unresolved_states))
    )).scalar() or 0

    pending_inv = (await session.execute(
        select(func.count(distinct(Investigation.id))).where(Investigation.status == "PENDING")
    )).scalar() or 0

    failed_inv = (await session.execute(
        select(func.count(distinct(Investigation.id))).where(Investigation.status.in_(["FAILED", "UNAVAILABLE"]))
    )).scalar() or 0

    pending_req = (await session.execute(
        select(func.count(distinct(ActionRequest.id))).where(ActionRequest.status == "PENDING_APPROVAL")
    )).scalar() or 0

    failed_exec = (await session.execute(
        select(func.count(distinct(ActionExecution.id))).where(ActionExecution.status == "FAILED")
    )).scalar() or 0

    unknown_exec = (await session.execute(
        select(func.count(distinct(ActionExecution.id))).where(ActionExecution.status == "UNKNOWN")
    )).scalar() or 0

    # Unreconciled: payments with no RECONCILED relationship
    reconciled_ids = select(ReconciliationRelationship.source_entity_id).where(
        ReconciliationRelationship.source_entity_type == "PAYMENT",
        ReconciliationRelationship.financial_status == FinancialEvaluationStatus.RECONCILED,
    )
    unreconciled = (await session.execute(
        select(func.count(distinct(Payment.id))).where(Payment.id.not_in(reconciled_ids))
    )).scalar() or 0

    open_periods = (await session.execute(
        select(func.count(distinct(FinancialPeriod.id))).where(FinancialPeriod.status == "OPEN")
    )).scalar() or 0

    closing_periods = (await session.execute(
        select(func.count(distinct(FinancialPeriod.id))).where(FinancialPeriod.status == "CLOSING")
    )).scalar() or 0

    # Blocked = OPEN/CLOSING period where latest evaluation has is_ready=False
    latest_eval_subq = (
        select(
            PeriodCloseEvaluation.period_id,
            func.max(PeriodCloseEvaluation.evaluated_at).label("latest_ts"),
        ).group_by(PeriodCloseEvaluation.period_id)
    ).subquery()
    blocked_q = (
        select(func.count(distinct(FinancialPeriod.id)))
        .join(latest_eval_subq, latest_eval_subq.c.period_id == FinancialPeriod.id)
        .join(
            PeriodCloseEvaluation,
            and_(
                PeriodCloseEvaluation.period_id == FinancialPeriod.id,
                PeriodCloseEvaluation.evaluated_at == latest_eval_subq.c.latest_ts,
            )
        )
        .where(
            FinancialPeriod.status.in_(["OPEN", "CLOSING"]),
            PeriodCloseEvaluation.is_ready == False,
        )
    )
    blocked_periods = (await session.execute(blocked_q)).scalar() or 0

    return OperationalRiskSummary(
        unresolved_exceptions=int(unresolved_exc),
        pending_investigations=int(pending_inv),
        failed_investigations=int(failed_inv),
        pending_action_requests=int(pending_req),
        failed_executions=int(failed_exec),
        unknown_executions=int(unknown_exec),
        unreconciled_transaction_count=int(unreconciled),
        open_periods=int(open_periods),
        closing_periods=int(closing_periods),
        blocked_periods=int(blocked_periods),
    )


# ─── PERIOD ANALYTICS ─────────────────────────────────────────────────────────

async def get_period_analytics(session: AsyncSession, limit: int = 20, offset: int = 0) -> PeriodAnalytics:
    total = (await session.execute(select(func.count(distinct(FinancialPeriod.id))))).scalar() or 0
    periods_q = select(FinancialPeriod).order_by(FinancialPeriod.start_date.desc()).limit(limit).offset(offset)
    period_rows = (await session.execute(periods_q)).scalars().all()

    items = []
    for p in period_rows:
        # Latest evaluation
        latest_eval = (await session.execute(
            select(PeriodCloseEvaluation)
            .where(PeriodCloseEvaluation.period_id == p.id)
            .order_by(PeriodCloseEvaluation.evaluated_at.desc())
            .limit(1)
        )).scalar_one_or_none()

        # Payment count within period boundaries
        pay_cnt = (await session.execute(
            select(func.count(distinct(Payment.id))).where(
                Payment.processed_at >= p.start_date,
                Payment.processed_at <= p.end_date,
            )
        )).scalar() or 0

        # Settlement count
        set_cnt = (await session.execute(
            select(func.count(distinct(Settlement.id))).where(
                Settlement.settlement_date >= p.start_date,
                Settlement.settlement_date <= p.end_date,
            )
        )).scalar() or 0

        # Exception count: discrepancies linked to payments in this period
        payment_ids_in_period = select(Payment.id).where(
            Payment.processed_at >= p.start_date,
            Payment.processed_at <= p.end_date,
        )
        exc_cnt = (await session.execute(
            select(func.count(distinct(Discrepancy.id))).where(
                Discrepancy.source_entity_id.in_(payment_ids_in_period),
                Discrepancy.source_entity_type == "PAYMENT",
            )
        )).scalar() or 0

        items.append(PeriodReportRow(
            id=p.id,
            period_name=p.period_name,
            start_date=p.start_date,
            end_date=p.end_date,
            status=p.status,
            last_readiness=latest_eval.is_ready if latest_eval else None,
            last_blocker_count=latest_eval.blocking_count if latest_eval else None,
            last_evaluated_at=latest_eval.evaluated_at if latest_eval else None,
            payment_count=int(pay_cnt),
            settlement_count=int(set_cnt),
            exception_count=int(exc_cnt),
        ))

    return PeriodAnalytics(items=items, total=int(total))


# ─── TREND ANALYTICS ─────────────────────────────────────────────────────────

async def get_trends(
    session: AsyncSession,
    metric: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    granularity: str = "day",
) -> TrendResponse:
    """Deterministic time-series aggregation.

    Timezone: All buckets are UTC date strings derived from the UTC timestamps
    stored in the database.  The response documents this clearly.

    Granularity: 'day' groups by date; 'week' by ISO week start; 'month' by
    year-month.  Using SQLAlchemy func.strftime for SQLite compatibility.
    """
    VALID_METRICS = {
        "payment_count", "payment_volume",
        "refund_count", "refund_volume",
        "settlement_count", "settlement_volume",
        "exception_count",
    }
    if metric not in VALID_METRICS:
        raise ValueError(f"Unsupported metric: {metric}. Valid: {sorted(VALID_METRICS)}")

    if granularity == "day":
        fmt = "%Y-%m-%d"
    elif granularity == "week":
        fmt = "%Y-W%W"
    elif granularity == "month":
        fmt = "%Y-%m"
    else:
        raise ValueError(f"Unsupported granularity: {granularity}")

    data: list[TrendPoint] = []

    if metric in ("payment_count", "payment_volume"):
        date_fn = func.strftime(fmt, Payment.processed_at).label("bucket")
        q = select(
            date_fn,
            Payment.currency,
            func.count(distinct(Payment.id)).label("cnt"),
            func.sum(Payment.amount).label("total"),
        ).group_by("bucket", Payment.currency).order_by("bucket")
        if start_date:
            q = q.where(Payment.processed_at >= start_date)
        if end_date:
            q = q.where(Payment.processed_at <= end_date)
        rows = (await session.execute(q)).all()
        for row in rows:
            value = Decimal(str(row.cnt)) if metric == "payment_count" else Decimal(str(row.total or 0))
            data.append(TrendPoint(bucket=row.bucket, currency=row.currency, metric=metric, value=value.quantize(Decimal("0.0001"))))

    elif metric in ("refund_count", "refund_volume"):
        date_fn = func.strftime(fmt, Refund.processed_at).label("bucket")
        q = select(
            date_fn,
            Refund.currency,
            func.count(distinct(Refund.id)).label("cnt"),
            func.sum(Refund.amount).label("total"),
        ).group_by("bucket", Refund.currency).order_by("bucket")
        if start_date:
            q = q.where(Refund.processed_at >= start_date)
        if end_date:
            q = q.where(Refund.processed_at <= end_date)
        rows = (await session.execute(q)).all()
        for row in rows:
            value = Decimal(str(row.cnt)) if metric == "refund_count" else Decimal(str(row.total or 0))
            data.append(TrendPoint(bucket=row.bucket, currency=row.currency, metric=metric, value=value.quantize(Decimal("0.0001"))))

    elif metric in ("settlement_count", "settlement_volume"):
        date_fn = func.strftime(fmt, Settlement.settlement_date).label("bucket")
        q = select(
            date_fn,
            Settlement.currency,
            func.count(distinct(Settlement.id)).label("cnt"),
            func.sum(Settlement.gross_amount).label("total"),
        ).group_by("bucket", Settlement.currency).order_by("bucket")
        if start_date:
            q = q.where(Settlement.settlement_date >= start_date)
        if end_date:
            q = q.where(Settlement.settlement_date <= end_date)
        rows = (await session.execute(q)).all()
        for row in rows:
            value = Decimal(str(row.cnt)) if metric == "settlement_count" else Decimal(str(row.total or 0))
            data.append(TrendPoint(bucket=row.bucket, currency=row.currency, metric=metric, value=value.quantize(Decimal("0.0001"))))

    elif metric == "exception_count":
        date_fn = func.strftime(fmt, Discrepancy.created_at).label("bucket")
        q = select(
            date_fn,
            func.count(distinct(Discrepancy.id)).label("cnt"),
        ).group_by("bucket").order_by("bucket")
        if start_date:
            q = q.where(Discrepancy.created_at >= start_date)
        if end_date:
            q = q.where(Discrepancy.created_at <= end_date)
        rows = (await session.execute(q)).all()
        for row in rows:
            data.append(TrendPoint(bucket=row.bucket, currency=None, metric=metric, value=Decimal(str(row.cnt))))

    return TrendResponse(metric=metric, granularity=granularity, timezone="UTC", data=data)


# ─── BREAKDOWN ANALYTICS ──────────────────────────────────────────────────────

async def get_breakdown(
    session: AsyncSession,
    dimension: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    period_id: Optional[str] = None,
) -> list[BreakdownItem]:
    """Breakdown by a supported dimension.

    Supported: 'provider', 'payment_method', 'merchant_id'
    Double-counting guard: Payment amounts come from Payment table directly.
    Refunds come from Refund table directly.
    Exceptions linked via Discrepancy.source_entity_id=Payment.id.
    """
    VALID_DIMENSIONS = {"provider", "payment_method", "merchant_id"}
    if dimension not in VALID_DIMENSIONS:
        raise ValueError(f"Unsupported dimension: {dimension}. Valid: {sorted(VALID_DIMENSIONS)}")

    start, end = await _resolve_period_dates(session, period_id, start_date, end_date)

    if dimension == "provider":
        dim_col = Payment.provider
    elif dimension == "payment_method":
        dim_col = Payment.payment_method_type
    else:  # merchant_id
        dim_col = Payment.merchant_id

    pay_q = select(
        dim_col.label("dim"),
        Payment.currency,
        func.count(distinct(Payment.id)).label("pay_cnt"),
        func.sum(Payment.amount).label("pay_vol"),
    ).group_by("dim", Payment.currency)
    if start:
        pay_q = pay_q.where(Payment.processed_at >= start)
    if end:
        pay_q = pay_q.where(Payment.processed_at <= end)
    pay_rows = (await session.execute(pay_q)).all()

    results: list[BreakdownItem] = []
    for pay_row in pay_rows:
        dim_val = pay_row.dim or "UNKNOWN"
        currency = pay_row.currency or "UNKNOWN"

        # Refunds: join Payment to get same dim value — safe because we SUM refund amounts not payment amounts
        if dimension == "provider":
            ref_dim_filter = (Payment.provider == dim_val)
        elif dimension == "payment_method":
            ref_dim_filter = (Payment.payment_method_type == dim_val)
        else:
            ref_dim_filter = (Payment.merchant_id == dim_val)

        ref_payment_ids = select(Payment.id).where(ref_dim_filter)
        if start:
            ref_payment_ids = ref_payment_ids.where(Payment.processed_at >= start)
        if end:
            ref_payment_ids = ref_payment_ids.where(Payment.processed_at <= end)

        ref_row = (await session.execute(
            select(
                func.count(distinct(Refund.id)).label("cnt"),
                func.sum(Refund.amount).label("total"),
            ).where(
                Refund.payment_id.in_(ref_payment_ids),
                Refund.currency == currency,
            )
        )).one()

        # Exception count linked to this dimension's payments
        exc_count = (await session.execute(
            select(func.count(distinct(Discrepancy.id))).where(
                Discrepancy.source_entity_type == "PAYMENT",
                Discrepancy.source_entity_id.in_(ref_payment_ids),
            )
        )).scalar() or 0

        results.append(BreakdownItem(
            dimension=dim_val,
            currency=currency,
            payment_count=int(pay_row.pay_cnt),
            payment_volume=Decimal(str(pay_row.pay_vol or 0)).quantize(Decimal("0.0001")),
            refund_count=int(ref_row.cnt or 0),
            refund_volume=Decimal(str(ref_row.total or 0)).quantize(Decimal("0.0001")),
            exception_count=int(exc_count),
        ))

    return sorted(results, key=lambda x: (-x.payment_count, x.dimension))


# ─── PERIOD COMPARISON ────────────────────────────────────────────────────────

async def get_period_comparison(
    session: AsyncSession,
    current_start: datetime,
    current_end: datetime,
    previous_start: datetime,
    previous_end: datetime,
) -> PeriodComparisonResponse:
    """Compare two date ranges.

    Safety rules:
    - Only compares currencies that appear in both periods.
    - Never subtracts USD from INR.
    - Zero-denominator percentages are returned as None.
    """
    async def _payment_vol(start, end) -> dict[str, Decimal]:
        rows = (await session.execute(
            select(Payment.currency, func.sum(Payment.amount).label("total"))
            .where(Payment.processed_at >= start, Payment.processed_at <= end)
            .group_by(Payment.currency)
        )).all()
        return {r.currency: Decimal(str(r.total or 0)) for r in rows}

    async def _refund_vol(start, end) -> dict[str, Decimal]:
        rows = (await session.execute(
            select(Refund.currency, func.sum(Refund.amount).label("total"))
            .where(Refund.processed_at >= start, Refund.processed_at <= end)
            .group_by(Refund.currency)
        )).all()
        return {r.currency: Decimal(str(r.total or 0)) for r in rows}

    curr_pay = await _payment_vol(current_start, current_end)
    prev_pay = await _payment_vol(previous_start, previous_end)
    curr_ref = await _refund_vol(current_start, current_end)
    prev_ref = await _refund_vol(previous_start, previous_end)

    rows: list[ComparisonRow] = []
    all_currencies = set(curr_pay) | set(prev_pay)

    for ccy in sorted(all_currencies):
        curr_val = curr_pay.get(ccy, Decimal("0"))
        prev_val = prev_pay.get(ccy, Decimal("0"))
        delta = curr_val - prev_val
        pct = float(delta / prev_val * 100) if prev_val != 0 else None
        rows.append(ComparisonRow(
            metric="payment_volume",
            currency=ccy,
            current_value=curr_val,
            previous_value=prev_val,
            absolute_delta=delta,
            percentage_delta=round(pct, 2) if pct is not None else None,
        ))

    all_ref_currencies = set(curr_ref) | set(prev_ref)
    for ccy in sorted(all_ref_currencies):
        curr_val = curr_ref.get(ccy, Decimal("0"))
        prev_val = prev_ref.get(ccy, Decimal("0"))
        delta = curr_val - prev_val
        pct = float(delta / prev_val * 100) if prev_val != 0 else None
        rows.append(ComparisonRow(
            metric="refund_volume",
            currency=ccy,
            current_value=curr_val,
            previous_value=prev_val,
            absolute_delta=delta,
            percentage_delta=round(pct, 2) if pct is not None else None,
        ))

    return PeriodComparisonResponse(
        current_start=current_start,
        current_end=current_end,
        previous_start=previous_start,
        previous_end=previous_end,
        rows=rows,
    )
