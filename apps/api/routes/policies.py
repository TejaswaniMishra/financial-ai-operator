from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db_session
from packages.schemas.policy import PolicyEvaluationRequest, PolicyEvaluationResponse
from services.policy.engine import PolicyEngine

router = APIRouter(prefix="/policies", tags=["Policies"])

@router.post("/evaluate", response_model=PolicyEvaluationResponse)
async def evaluate_policy(
    request: PolicyEvaluationRequest,
    db: AsyncSession = Depends(get_db_session)
):
    engine = PolicyEngine(db)

    try:
        evaluation = await engine.evaluate(request.investigation_id, request.action)
        return PolicyEvaluationResponse(
            policy_decision_id=evaluation.id,
            action=evaluation.action,
            decision=evaluation.decision,
            rule_code=evaluation.rule_code,
            reason=evaluation.reason,
            approval_required=evaluation.approval_required
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred during policy evaluation.")
