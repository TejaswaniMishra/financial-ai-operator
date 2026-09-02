import uuid
import asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError, InvalidRequestError

from database.models.action_request import ActionRequest, ActionRequestStatus
from database.models.action_execution import ActionExecution, ActionExecutionAttempt, ActionExecutionStatus
from services.action_execution.adapter import ActionExecutionAdapter
from services.action_execution.simulator import SimulatedExecutionAdapter

class ExecutionError(Exception):
    pass

from sqlalchemy.orm import selectinload

class ActionExecutionService:
    def __init__(self, db: AsyncSession, adapter: ActionExecutionAdapter = None):
        self.db = db
        self.adapter = adapter or SimulatedExecutionAdapter()

    async def execute_action_request(self, request_id: str, idempotency_key: str = None) -> ActionExecution:
        """
        Safely execute an ActionRequest via the assigned adapter.
        """
        # 1. Authorize: Load request and verify it is APPROVED
        stmt = select(ActionRequest).where(ActionRequest.id == request_id)
        action_request = (await self.db.execute(stmt)).scalar_one_or_none()
        
        if not action_request:
            raise ExecutionError(f"ActionRequest {request_id} not found")
            
        if action_request.status != ActionRequestStatus.APPROVED:
            raise ExecutionError(f"ActionRequest {request_id} cannot be executed. Status is {action_request.status.value}")
            
        # 2. Idempotency Key Generation
        if not idempotency_key:
            idempotency_key = f"exec_{request_id}"
            
        # 3. Create or Reuse ActionExecution safely (Concurrency handling)
        execution = await self._get_or_create_execution(action_request, idempotency_key)
        
        # 4. Check if execution is already successfully finished or running
        if execution.status == ActionExecutionStatus.SUCCEEDED:
            return execution
        if execution.status == ActionExecutionStatus.RUNNING:
            raise ExecutionError(f"Execution {execution.id} is already RUNNING")
            
        # Do NOT auto-retry UNKNOWN
        if execution.status == ActionExecutionStatus.UNKNOWN:
            raise ExecutionError(f"Execution {execution.id} is UNKNOWN. Manual review required. Will not auto-retry.")
            
        # We can execute if status is PENDING or FAILED (retry)
        
        # 5. Preflight Validation
        # In a real system, we'd check action parameters here. For M7, just basic validation.
        
        # 6. Mark as RUNNING and create attempt
        execution.status = ActionExecutionStatus.RUNNING
        execution.started_at = datetime.now(timezone.utc).replace(tzinfo=None)
        
        stmt_attempts = select(ActionExecutionAttempt).where(ActionExecutionAttempt.action_execution_id == execution.id)
        attempts = (await self.db.execute(stmt_attempts)).scalars().all()
        attempt_number = len(attempts) + 1
        
        attempt = ActionExecutionAttempt(
            action_execution_id=execution.id,
            attempt_number=attempt_number,
            status=ActionExecutionStatus.RUNNING
        )
        self.db.add(attempt)
        await self.db.commit()
        await self.db.refresh(execution)
        await self.db.refresh(attempt)
        
        # 7. Invoke Adapter
        try:
            # We don't hold the DB transaction open during external execution!
            result = await self.adapter.execute(action_request, idempotency_key)
            
            # 8. Handle Result
            execution.status = result.status
            execution.result = result.result_data
            execution.error_code = result.error_code
            execution.error_message = result.error_message
            execution.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            
            attempt.status = result.status
            attempt.result = result.result_data
            attempt.error_code = result.error_code
            attempt.error_message = result.error_message
            attempt.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            
            await self.db.commit()
            return await self._get_execution(execution.id)
            
        except Exception as e:
            # Catch unexpected exceptions (e.g., adapter crashed) and treat as UNKNOWN
            # if we can't be sure the execution didn't partially happen.
            # For pure code exceptions, it might be FAILED, but UNKNOWN is safer for financial ops.
            await self.db.rollback()
            
            execution = await self._get_execution(execution.id)
            attempt = await self._get_attempt(attempt.id)
            
            execution.status = ActionExecutionStatus.UNKNOWN
            execution.error_code = "UNEXPECTED_ERROR"
            execution.error_message = str(e)
            execution.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            
            attempt.status = ActionExecutionStatus.UNKNOWN
            attempt.error_code = "UNEXPECTED_ERROR"
            attempt.error_message = str(e)
            attempt.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            
            await self.db.commit()
            return await self._get_execution(execution.id)

    async def _get_or_create_execution(self, action_request: ActionRequest, idempotency_key: str) -> ActionExecution:
        # Check existing
        stmt = select(ActionExecution).options(selectinload(ActionExecution.attempts)).where(ActionExecution.idempotency_key == idempotency_key)
        existing = (await self.db.execute(stmt)).scalar_one_or_none()
        if existing:
            return existing
            
        execution = ActionExecution(
            action_request_id=action_request.id,
            idempotency_key=idempotency_key,
            execution_type="simulation",
            adapter=self.adapter.name,
            status=ActionExecutionStatus.PENDING
        )
        self.db.add(execution)
        
        try:
            await self.db.commit()
            return await self._get_execution(execution.id)
        except (IntegrityError, InvalidRequestError):
            await self.db.rollback()
            # Concurrency fallback
            for _ in range(3):
                existing = (await self.db.execute(stmt)).scalar_one_or_none()
                if existing:
                    return existing
                await asyncio.sleep(0.05)
            raise ExecutionError(f"Failed to resolve execution for key {idempotency_key} due to concurrency.")
            
    async def _get_execution(self, id: str) -> ActionExecution:
        stmt = select(ActionExecution).options(selectinload(ActionExecution.attempts)).where(ActionExecution.id == id)
        return (await self.db.execute(stmt)).scalar_one_or_none()
        
    async def _get_attempt(self, id: str) -> ActionExecutionAttempt:
        stmt = select(ActionExecutionAttempt).where(ActionExecutionAttempt.id == id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_executions_for_request(self, request_id: str) -> list[ActionExecution]:
        stmt = select(ActionExecution).options(selectinload(ActionExecution.attempts)).where(ActionExecution.action_request_id == request_id).order_by(ActionExecution.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
