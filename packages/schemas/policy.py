from pydantic import BaseModel
from database.models.policy import PolicyAction, PolicyDecision

class PolicyEvaluationRequest(BaseModel):
    investigation_id: str
    action: PolicyAction

class PolicyEvaluationResponse(BaseModel):
    policy_decision_id: str
    action: PolicyAction
    decision: PolicyDecision
    rule_code: str
    reason: str
    approval_required: bool
