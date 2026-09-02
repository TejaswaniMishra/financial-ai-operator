from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List
from datetime import datetime
from database.models.action_execution import ActionExecutionStatus

class ActionExecutionAttemptResponse(BaseModel):
    id: str
    action_execution_id: str
    attempt_number: int
    status: ActionExecutionStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ActionExecutionResponse(BaseModel):
    id: str
    action_request_id: str
    idempotency_key: str
    status: ActionExecutionStatus
    execution_type: str
    adapter: str
    requested_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    attempts: List[ActionExecutionAttemptResponse] = []

    class Config:
        from_attributes = True

class ActionExecutionRequest(BaseModel):
    # Depending on the contract, some executions might require an explicitly provided idempotency key
    idempotency_key: Optional[str] = Field(None, description="Optional caller-provided idempotency key.")
