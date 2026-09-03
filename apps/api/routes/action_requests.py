from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from apps.api.auth import get_current_user
from apps.api.authorization import require_permission
from apps.api.dependencies import get_db_session
from packages.rbac.permissions import Permission
from packages.schemas.action_request import (
    ActionRequestCreate,
    ActionRequestResponse,
    ActionRequestApprove,
    ActionRequestReject,
    ActionRequestCancel
)
from services.action_request.service import ActionRequestService
from database.models.action_request import ActionRequest

router = APIRouter(
    prefix="/action-requests",
    tags=["Action Requests"],
    dependencies=[Depends(get_current_user)]
)

@router.post("", response_model=ActionRequestResponse, dependencies=[Depends(require_permission(Permission.VIEW_ACTION_REQUESTS))])
async def create_action_request(
    request: ActionRequestCreate,
    db: AsyncSession = Depends(get_db_session)
):
    service = ActionRequestService(db)
    try:
        ar = await service.create_from_evaluation(
            policy_evaluation_id=request.policy_evaluation_id,
            requested_source=request.requested_source
        )
        return ar
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("", response_model=List[ActionRequestResponse], dependencies=[Depends(require_permission(Permission.VIEW_ACTION_REQUESTS))])
async def list_action_requests(
    db: AsyncSession = Depends(get_db_session)
):
    stmt = select(ActionRequest)
    results = (await db.execute(stmt)).scalars().all()
    return results

@router.get("/{request_id}", response_model=ActionRequestResponse, dependencies=[Depends(require_permission(Permission.VIEW_ACTION_REQUESTS))])
async def get_action_request(
    request_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    service = ActionRequestService(db)
    try:
        return await service.get_request(request_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.post("/{request_id}/approve", response_model=ActionRequestResponse, dependencies=[Depends(require_permission(Permission.APPROVE_ACTION_REQUEST))])
async def approve_action_request(
    request_id: str,
    payload: ActionRequestApprove,
    db: AsyncSession = Depends(get_db_session)
):
    service = ActionRequestService(db)
    try:
        return await service.approve_action_request(request_id, actor=payload.actor)
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{request_id}/reject", response_model=ActionRequestResponse, dependencies=[Depends(require_permission(Permission.REJECT_ACTION_REQUEST))])
async def reject_action_request(
    request_id: str,
    payload: ActionRequestReject,
    db: AsyncSession = Depends(get_db_session)
):
    service = ActionRequestService(db)
    try:
        return await service.reject_action_request(request_id, reason=payload.reason, actor=payload.actor)
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/{request_id}/cancel", response_model=ActionRequestResponse, dependencies=[Depends(require_permission(Permission.CANCEL_ACTION_REQUEST))])
async def cancel_action_request(
    request_id: str,
    payload: ActionRequestCancel,
    db: AsyncSession = Depends(get_db_session)
):
    service = ActionRequestService(db)
    try:
        return await service.cancel_action_request(request_id, reason=payload.reason, actor=payload.actor)
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

from packages.schemas.action_execution import ActionExecutionResponse, ActionExecutionRequest
from services.action_execution.service import ActionExecutionService, ExecutionError

@router.post("/{request_id}/execute", response_model=ActionExecutionResponse, dependencies=[Depends(require_permission(Permission.EXECUTE_ACTION))])
async def execute_action_request(
    request_id: str,
    payload: ActionExecutionRequest,
    db: AsyncSession = Depends(get_db_session)
):
    service = ActionExecutionService(db)
    try:
        execution = await service.execute_action_request(
            request_id=request_id,
            idempotency_key=payload.idempotency_key
        )
        return execution
    except ExecutionError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{request_id}/executions", response_model=List[ActionExecutionResponse], dependencies=[Depends(require_permission(Permission.VIEW_ACTION_REQUESTS))])
async def list_action_request_executions(
    request_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    service = ActionExecutionService(db)
    executions = await service.get_executions_for_request(request_id)
    return executions
