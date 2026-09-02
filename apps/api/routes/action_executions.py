from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from apps.api.auth import get_current_user
from apps.api.dependencies import get_db_session
from packages.schemas.action_execution import ActionExecutionResponse
from database.models.action_execution import ActionExecution

router = APIRouter(
    prefix="/action-executions", 
    tags=["Action Executions"],
    dependencies=[Depends(get_current_user)]
)

@router.get("", response_model=List[ActionExecutionResponse])
async def list_action_executions(
    db: AsyncSession = Depends(get_db_session)
):
    stmt = select(ActionExecution).order_by(ActionExecution.created_at.desc())
    results = (await db.execute(stmt)).scalars().all()
    return results

@router.get("/{execution_id}", response_model=ActionExecutionResponse)
async def get_action_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    stmt = select(ActionExecution).where(ActionExecution.id == execution_id)
    execution = (await db.execute(stmt)).scalar_one_or_none()
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ActionExecution {execution_id} not found")
    return execution
