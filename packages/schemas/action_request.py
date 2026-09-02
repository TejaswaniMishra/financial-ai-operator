from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from database.models.action_request import ActionRequestStatus

class ActionRequestCreate(BaseModel):
    policy_evaluation_id: str
    requested_source: Optional[str] = None

class ActionRequestResponse(BaseModel):
    id: str
    investigation_id: str
    discrepancy_id: Optional[str] = None
    policy_evaluation_id: str
    action: str
    status: ActionRequestStatus
    requested_source: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ActionRequestApprove(BaseModel):
    actor: Optional[str] = None

class ActionRequestReject(BaseModel):
    reason: str
    actor: Optional[str] = None

class ActionRequestCancel(BaseModel):
    reason: str
    actor: Optional[str] = None
