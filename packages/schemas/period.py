from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class PeriodStatus(str, Enum):
    OPEN = "OPEN"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"


class ControlStatus(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    BLOCKED = "BLOCKED"


class ControlSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class CloseControlCode(str, Enum):
    CLOSE_UNRECONCILED_TRANSACTIONS = "CLOSE_UNRECONCILED_TRANSACTIONS"
    CLOSE_UNRESOLVED_EXCEPTIONS = "CLOSE_UNRESOLVED_EXCEPTIONS"
    CLOSE_PENDING_INVESTIGATIONS = "CLOSE_PENDING_INVESTIGATIONS"
    CLOSE_FAILED_INVESTIGATIONS = "CLOSE_FAILED_INVESTIGATIONS"
    CLOSE_UNAVAILABLE_INVESTIGATIONS = "CLOSE_UNAVAILABLE_INVESTIGATIONS"
    CLOSE_PENDING_ACTION_REQUESTS = "CLOSE_PENDING_ACTION_REQUESTS"
    CLOSE_RUNNING_EXECUTIONS = "CLOSE_RUNNING_EXECUTIONS"
    CLOSE_UNKNOWN_EXECUTIONS = "CLOSE_UNKNOWN_EXECUTIONS"
    CLOSE_DATA_QUALITY_ERRORS = "CLOSE_DATA_QUALITY_ERRORS"
    CLOSE_DUPLICATE_INGESTION = "CLOSE_DUPLICATE_INGESTION"
    CLOSE_ORPHAN_RECORDS = "CLOSE_ORPHAN_RECORDS"


class CloseControlResult(BaseModel):
    control_code: CloseControlCode
    status: ControlStatus
    severity: ControlSeverity
    count: int
    amount_by_currency: Optional[Dict[str, float]] = None
    explanation: str
    related_ids: Optional[List[str]] = None


class CurrencyMetrics(BaseModel):
    transaction_count: int = 0
    total_amount: float = 0.0
    payments_count: int = 0
    payments_amount: float = 0.0
    refunds_count: int = 0
    refunds_amount: float = 0.0
    fees_count: int = 0
    fees_amount: float = 0.0
    settlements_count: int = 0
    settlements_amount: float = 0.0
    bank_transactions_count: int = 0
    bank_transactions_amount: float = 0.0


class PeriodMetrics(BaseModel):
    metrics_by_currency: Dict[str, CurrencyMetrics]
    reconciled_count: int = 0
    unreconciled_count: int = 0
    discrepancy_count: int = 0
    investigation_count: int = 0
    action_request_count: int = 0
    execution_failures: int = 0
    execution_unknowns: int = 0


class CloseReadiness(BaseModel):
    period_id: str
    is_ready: bool
    overall_status: ControlStatus
    controls: List[CloseControlResult]
    metrics: PeriodMetrics
    evaluated_at: datetime


class PeriodCreate(BaseModel):
    period_name: str
    start_date: datetime
    end_date: datetime


class PeriodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    period_name: str
    start_date: datetime
    end_date: datetime
    status: PeriodStatus
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    closed_by: Optional[str] = None


class PeriodListResponse(BaseModel):
    items: List[PeriodResponse]
    total: int
    page: int
    size: int


class PeriodCloseEvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    period_id: str
    evaluated_at: datetime
    evaluated_by: str
    is_ready: bool
    blocking_count: int
    warning_count: int
    control_results: List[Dict[str, Any]]
    metrics_snapshot: Dict[str, Any]


class PeriodDetailResponse(BaseModel):
    period: PeriodResponse
    metrics: PeriodMetrics
    readiness: CloseReadiness
    latest_evaluation: Optional[PeriodCloseEvaluationResponse] = None
