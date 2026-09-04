from enum import Enum
from typing import Optional, Any
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict

from packages.schemas.reconciliation import DiscrepancyType, Severity

class OverallExceptionState(str, Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    RESOLVED = "RESOLVED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"

class ExceptionReadSummary(BaseModel):
    id: str
    type: DiscrepancyType
    severity: Severity
    overall_state: OverallExceptionState
    amount: Optional[Decimal]
    currency: Optional[str]
    source_entity_type: str
    source_entity_id: str
    detected_at: datetime
    
    investigation_status: Optional[str] = None
    policy_decision: Optional[str] = None
    action_request_status: Optional[str] = None
    execution_status: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class ExceptionListResponse(BaseModel):
    items: list[ExceptionReadSummary]
    total: int
    page: int
    size: int

class ExceptionDetail(BaseModel):
    id: str
    type: DiscrepancyType
    severity: Severity
    overall_state: OverallExceptionState
    amount: Optional[Decimal]
    expected_amount: Optional[Decimal] = None
    actual_amount: Optional[Decimal] = None
    difference_amount: Optional[Decimal] = None
    currency: Optional[str]
    source_entity_type: str
    source_entity_id: str
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[str] = None
    detected_at: datetime
    run_id: str
    rule_code: str
    
    investigation_status: Optional[str] = None
    investigation_id: Optional[str] = None
    root_cause: Optional[str] = None
    investigation_explanation: Optional[str] = None
    
    policy_decision: Optional[str] = None
    policy_action: Optional[str] = None
    policy_rule_code: Optional[str] = None
    policy_reason: Optional[str] = None
    
    action_request_id: Optional[str] = None
    action_request_status: Optional[str] = None
    action_request_action: Optional[str] = None
    
    execution_id: Optional[str] = None
    execution_status: Optional[str] = None
    execution_error: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)
