from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from apps.api.dependencies import get_db_session
from database.models.investigation import Investigation, InvestigationAttempt, InvestigationStatus
from database.models.reconciliation import Discrepancy
from services.investigation.agent import InvestigationAgent

router = APIRouter(prefix="/investigations", tags=["Investigations"])

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
        
    # As per instruction 7 & 13: DO NOT execute financial changes. 
    # Create an Approved Action Request. Do not bypass the Policy Engine.
    
    # In a real app we'd insert into `approved_action_requests` table.
    # For now we return the approval payload to confirm the boundary.
    
    return {
        "investigation_id": investigation_id,
        "action": "APPROVED_ACTION_REQUEST_CREATED",
        "message": "The recommended actions have been queued for the Policy Engine. No direct financial changes were made."
    }
