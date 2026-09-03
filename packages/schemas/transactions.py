"""M9 — Transaction workspace read-only schemas.

Explicit safe response contracts for the unified financial transaction
workspace. The backend remains authoritative; these schemas expose only
deterministic financial facts and derived reconciliation/investigation/action
state. No ORM objects, credentials, prompts, or internal diagnostics.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field

TRANSACTION_TYPES = (
    "PAYMENT",
    "REFUND",
    "FEE",
    "SETTLEMENT",
    "BANK_TRANSACTION",
)


class TransactionRecord(BaseModel):
    """One row in the transaction workspace list (unified read model)."""

    id: str
    record_type: str  # one of TRANSACTION_TYPES
    external_id: Optional[str] = None
    merchant_id: str
    merchant_name: str
    provider: Optional[str] = None
    amount: Decimal
    currency: str
    status: str
    created_at: datetime
    # Derived state (backend-computed from reconciliation/discrepancy tables):
    reconciled: bool = False
    has_discrepancy: bool = False


class TransactionSummary(BaseModel):
    """Real per-type counts matching the current filter set (no fake KPIs)."""

    PAYMENT: int = 0
    REFUND: int = 0
    FEE: int = 0
    SETTLEMENT: int = 0
    BANK_TRANSACTION: int = 0
    total: int = 0


class TransactionListResponse(BaseModel):
    items: list[TransactionRecord]
    total: int
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    summary: TransactionSummary


class MerchantRef(BaseModel):
    id: str
    name: str


class OrderRef(BaseModel):
    id: str
    external_id: Optional[str] = None
    status: str
    amount: Decimal
    currency: str


class CustomerRef(BaseModel):
    id: str
    display_name: str


class RelatedRecord(BaseModel):
    """Safest minimal facts about a related financial record."""

    id: str
    record_type: str
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None


class ReconciliationContext(BaseModel):
    """Derived reconciliation state for this record (backend-computed)."""

    relationship_id: str
    relationship_type: str
    relationship_status: str
    financial_status: str
    run_id: str
    run_status: str
    source_entity_type: str
    source_entity_id: str
    target_entity_type: str
    target_entity_id: str


class DiscrepancyContext(BaseModel):
    id: str
    rule_code: str
    discrepancy_type: str
    severity: str
    expected_amount: Optional[Decimal] = None
    actual_amount: Optional[Decimal] = None
    difference_amount: Optional[Decimal] = None
    currency: Optional[str] = None
    run_id: str


class InvestigationContext(BaseModel):
    id: str
    discrepancy_id: str
    status: str
    created_at: Optional[datetime] = None


class ActionRequestContext(BaseModel):
    id: str
    investigation_id: str
    discrepancy_id: Optional[str] = None
    action: str
    status: str
    created_at: Optional[datetime] = None


class ActionExecutionContext(BaseModel):
    id: str
    action_request_id: str
    status: str
    execution_type: str
    adapter: str
    requested_at: Optional[datetime] = None
    error_code: Optional[str] = None


class TransactionDetail(BaseModel):
    """Full authoritative detail for one financial record."""

    id: str
    record_type: str
    external_id: Optional[str] = None
    merchant: MerchantRef
    provider: Optional[str] = None
    amount: Decimal
    currency: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Relationship context where it actually exists in the database.
    order: Optional[OrderRef] = None
    customer: Optional[CustomerRef] = None
    related: list[RelatedRecord] = Field(default_factory=list)

    # Derived reconciliation / exception / action state.
    reconciliation: list[ReconciliationContext] = Field(default_factory=list)
    discrepancies: list[DiscrepancyContext] = Field(default_factory=list)
    investigation: Optional[InvestigationContext] = None
    action_requests: list[ActionRequestContext] = Field(default_factory=list)
    executions: list[ActionExecutionContext] = Field(default_factory=list)


class LineageNode(BaseModel):
    """One node in the transaction lineage.

    `role` distinguishes SOURCE financial facts (payments, settlements, bank
    transactions) from DERIVED reconciliation/investigation/action state so
    the UI never presents derived state as an authoritative financial fact.
    """

    kind: str
    role: str  # "SOURCE" | "DERIVED"
    id: str
    label: str
    status: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    timestamp: Optional[datetime] = None
    detail: dict[str, Any] = Field(default_factory=dict)


class TransactionLineageResponse(BaseModel):
    record_type: str
    record_id: str
    nodes: list[LineageNode]