"""Strictly-typed Pydantic schemas for M12 Financial Reporting.

All financial amounts are represented at currency level — currencies are
NEVER aggregated across different ISO codes.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional
from datetime import datetime

from pydantic import BaseModel


# ─── Currency-aware leaf types ────────────────────────────────────────────────

class AmountByCurrency(BaseModel):
    """A single amount isolated to one ISO 4217 currency."""
    currency: str
    count: int = 0
    total_amount: Decimal = Decimal("0.0000")


# ─── Executive Summary ────────────────────────────────────────────────────────

class ExecutiveSummary(BaseModel):
    """Top-level KPI block.  Every monetary metric is per-currency.
    Never aggregated across currencies.
    """
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    period_id: Optional[str] = None

    payment_volume: list[AmountByCurrency]
    refund_volume: list[AmountByCurrency]
    fee_volume: list[AmountByCurrency]
    settlement_volume: list[AmountByCurrency]
    bank_transaction_volume: list[AmountByCurrency]

    total_payment_count: int
    total_refund_count: int
    total_fee_count: int
    total_settlement_count: int
    total_bank_transaction_count: int

    reconciled_count: int
    unreconciled_count: int
    discrepancy_count: int
    unresolved_exception_count: int
    investigation_count: int
    pending_action_request_count: int
    failed_execution_count: int
    unknown_execution_count: int


# ─── Financial Flow ───────────────────────────────────────────────────────────

class FinancialFlowStage(BaseModel):
    """Volume for a single stage (Payment, Refund, Fee, Settlement, Bank) per currency."""
    stage: str  # "PAYMENT" | "REFUND" | "FEE" | "SETTLEMENT" | "BANK_TRANSACTION"
    currency: str
    count: int
    total_amount: Decimal


class FinancialFlowSummary(BaseModel):
    """
    Ordered pipeline of financial stages.
    Each row is (stage, currency) pair — amounts are NEVER cross-currency.
    """
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    stages: list[FinancialFlowStage]


# ─── Reconciliation Analytics ─────────────────────────────────────────────────

class ReconciliationAnalytics(BaseModel):
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None

    # Total Payment records evaluated in this date range
    total_payments_eligible: int
    reconciled_count: int
    unreconciled_count: int
    # reconciled_count / total_payments_eligible  (None if denominator = 0)
    reconciliation_rate: Optional[float]

    discrepancy_count: int
    discrepancy_amount_by_currency: list[AmountByCurrency]

    # ReconciliationRelationship counts by financial_status
    relationship_reconciled: int
    relationship_discrepancy: int
    relationship_unresolved: int


# ─── Exception Analytics ──────────────────────────────────────────────────────

class ExceptionStateCount(BaseModel):
    state: str
    count: int


class ExceptionTypeCount(BaseModel):
    type: str
    count: int


class RootCauseCount(BaseModel):
    root_cause: str
    count: int


class ExceptionAnalytics(BaseModel):
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None

    total_exceptions: int
    by_state: list[ExceptionStateCount]
    by_type: list[ExceptionTypeCount]
    by_root_cause: list[RootCauseCount]
    unresolved_amount_by_currency: list[AmountByCurrency]


# ─── Operational Risk ─────────────────────────────────────────────────────────

class OperationalRiskSummary(BaseModel):
    """Operational health indicators — clearly labelled as indicators,
    NOT financial-risk scores.
    """
    unresolved_exceptions: int
    pending_investigations: int
    failed_investigations: int
    pending_action_requests: int
    failed_executions: int
    unknown_executions: int
    unreconciled_transaction_count: int
    open_periods: int
    closing_periods: int
    blocked_periods: int   # OPEN/CLOSING periods where last evaluation was BLOCKED


# ─── Period Analytics ─────────────────────────────────────────────────────────

class PeriodReportRow(BaseModel):
    id: str
    period_name: str
    start_date: datetime
    end_date: datetime
    status: str
    last_readiness: Optional[bool] = None
    last_blocker_count: Optional[int] = None
    last_evaluated_at: Optional[datetime] = None
    payment_count: int
    settlement_count: int
    exception_count: int


class PeriodAnalytics(BaseModel):
    items: list[PeriodReportRow]
    total: int


# ─── Trend Analytics ─────────────────────────────────────────────────────────

class TrendPoint(BaseModel):
    """One data point for a time-series chart.

    timezone: All bucket dates are UTC date strings.
    """
    bucket: str           # ISO date string e.g. "2024-01-15"
    currency: Optional[str] = None
    metric: str           # "payment_volume" | "payment_count" | etc.
    value: Decimal


class TrendResponse(BaseModel):
    metric: str
    granularity: str      # "day" | "week" | "month"
    timezone: str = "UTC"
    data: list[TrendPoint]


# ─── Period Comparison ────────────────────────────────────────────────────────

class ComparisonRow(BaseModel):
    metric: str
    currency: Optional[str]
    current_value: Decimal
    previous_value: Decimal
    absolute_delta: Decimal
    percentage_delta: Optional[float]   # None if previous_value = 0


class PeriodComparisonResponse(BaseModel):
    current_start: datetime
    current_end: datetime
    previous_start: datetime
    previous_end: datetime
    rows: list[ComparisonRow]


# ─── Breakdown Analytics ──────────────────────────────────────────────────────

class BreakdownItem(BaseModel):
    dimension: str          # value of the grouping key
    currency: str
    payment_count: int
    payment_volume: Decimal
    refund_count: int
    refund_volume: Decimal
    exception_count: int
