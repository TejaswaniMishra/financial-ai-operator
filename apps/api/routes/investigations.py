from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from apps.api.auth import get_current_user
from apps.api.dependencies import get_db_session
from database.models.investigation import Investigation, InvestigationAttempt, InvestigationStatus
from database.models.reconciliation import Discrepancy
from services.investigation.agent import InvestigationAgent

router = APIRouter(
    prefix="/investigations",
    tags=["Investigations"],
    dependencies=[Depends(get_current_user)]
)

@router.get("")
async def list_investigations(
    db: AsyncSession = Depends(get_db_session)
):
    stmt = select(Investigation).order_by(Investigation.created_at.desc())
    investigations = (await db.execute(stmt)).scalars().all()
    
    return [{
        "id": inv.id,
        "discrepancy_id": inv.discrepancy_id,
        "status": inv.status.value if hasattr(inv.status, 'value') else str(inv.status),
        "active_attempt_id": inv.active_attempt_id,
        "created_at": inv.created_at.isoformat() if inv.created_at else None
    } for inv in investigations]

@router.post("/discrepancy/{discrepancy_id}/run")
async def run_investigation(
    discrepancy_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    # Verify discrepancy exists
    stmt = select(Discrepancy).where(Discrepancy.id == discrepancy_id)
    discrepancy = (await db.execute(stmt)).scalar_one_or_none()
    if not discrepancy:
        raise HTTPException(status_code=404, detail="Discrepancy not found")
        
    agent = InvestigationAgent(db)
    attempt = await agent.run_investigation(discrepancy_id)
    
    return {
        "investigation_id": attempt.investigation_id,
        "attempt_id": attempt.id,
        "status": attempt.investigation.status.value if hasattr(attempt.investigation.status, 'value') else str(attempt.investigation.status),
        "is_valid": attempt.is_valid,
        "result": attempt.validated_output if attempt.is_valid else None,
        "errors": attempt.validation_errors
    }

@router.get("/{investigation_id}")
async def get_investigation(
    investigation_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    stmt = select(Investigation).where(Investigation.id == investigation_id)
    investigation = (await db.execute(stmt)).scalar_one_or_none()
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
        
    return {
        "id": investigation.id,
        "discrepancy_id": investigation.discrepancy_id,
        "status": investigation.status.value if hasattr(investigation.status, 'value') else str(investigation.status),
        "active_attempt_id": investigation.active_attempt_id,
        "created_at": investigation.created_at.isoformat() if investigation.created_at else None
    }

@router.get("/{investigation_id}/attempts")
async def get_investigation_attempts(
    investigation_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    stmt = select(InvestigationAttempt).where(
        InvestigationAttempt.investigation_id == investigation_id
    ).order_by(InvestigationAttempt.created_at.desc())
    
    attempts = (await db.execute(stmt)).scalars().all()
    
    return [{
        "id": a.id,
        "prompt_version": a.prompt_version,
        "model_used": a.model_used,
        "is_valid": a.is_valid,
        "created_at": a.created_at.isoformat() if a.created_at else None
    } for a in attempts]

@router.get("/{investigation_id}/attempts/{attempt_id}")
async def get_investigation_attempt(
    investigation_id: str,
    attempt_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    stmt = select(InvestigationAttempt).options(selectinload(InvestigationAttempt.investigation)).where(
        InvestigationAttempt.id == attempt_id,
        InvestigationAttempt.investigation_id == investigation_id
    )
    attempt = (await db.execute(stmt)).scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Investigation attempt not found")

    return {
        "investigation_id": attempt.investigation_id,
        "attempt_id": attempt.id,
        "status": attempt.investigation.status.value if hasattr(attempt.investigation.status, 'value') else str(attempt.investigation.status),
        "is_valid": attempt.is_valid,
        "result": attempt.validated_output,
        "errors": attempt.validation_errors
    }

@router.post("/{investigation_id}/approve")
async def approve_investigation(
    investigation_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    stmt = select(Investigation).where(Investigation.id == investigation_id)
    investigation = (await db.execute(stmt)).scalar_one_or_none()
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
        
    if investigation.status != InvestigationStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Can only approve completed investigations")
        
    from services.policy.engine import PolicyEngine
    from database.models.policy import PolicyAction, PolicyDecision
    from services.action_request.service import ActionRequestService

    # We use RESOLVE_DISCREPANCY as the default action for an investigation approval
    engine = PolicyEngine(db)
    evaluation = await engine.evaluate(investigation_id, PolicyAction.RESOLVE_DISCREPANCY)
    
    action_request_id = None
    if evaluation.decision == PolicyDecision.APPROVAL_REQUIRED:
        ar_service = ActionRequestService(db)
        action_request = await ar_service.create_from_evaluation(evaluation.id)
        action_request_id = action_request.id
    
    return {
        "investigation_id": investigation_id,
        "policy_decision_id": evaluation.id,
        "action_request_id": action_request_id,
        "action": evaluation.action.value if hasattr(evaluation.action, 'value') else str(evaluation.action),
        "decision": evaluation.decision.value if hasattr(evaluation.decision, 'value') else str(evaluation.decision),
        "rule_code": evaluation.rule_code,
        "reason": evaluation.reason,
        "approval_required": evaluation.approval_required,
        "message": "The recommended actions have been processed by the Policy Engine. No direct financial changes were made."
    }
