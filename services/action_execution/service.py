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

from services.auth.security_events import action_execution_started, action_execution_succeeded, action_execution_failed

class ActionExecutionService:
    def __init__(self, db: AsyncSession, adapter: ActionExecutionAdapter = None):
        self.db = db
        self.adapter = adapter or SimulatedExecutionAdapter()

    async def execute_action_request(self, request_id: str, idempotency_key: str = None, actor_id: str = None) -> ActionExecution:
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
            
        # 3. Global Request Guard
        # Check all existing executions for this request.
        stmt_execs = select(ActionExecution).options(selectinload(ActionExecution.attempts)).where(ActionExecution.action_request_id == request_id)
        existing_executions = (await self.db.execute(stmt_execs)).scalars().all()
        
        for ex in existing_executions:
            if ex.idempotency_key == idempotency_key:
                # Idempotent return of the EXACT same execution attempt
                return ex
                
            if ex.status in (ActionExecutionStatus.SUCCEEDED, ActionExecutionStatus.RUNNING, ActionExecutionStatus.UNKNOWN):
                # A DIFFERENT execution attempt is already successful, running, or stuck in unknown.
                raise ExecutionError(f"ActionRequest {request_id} already has an execution in status {ex.status.value}. Cannot start a new execution.")

        # 4. Idempotency Ownership Claim
        # If we get here, no conflicting executions exist. We try to claim ownership by inserting.
        execution_id = str(uuid.uuid4())
        execution = ActionExecution(
            id=execution_id,
            action_request_id=action_request.id,
            idempotency_key=idempotency_key,
            execution_type="simulation",
            adapter=self.adapter.name,
            status=ActionExecutionStatus.PENDING
        )
        self.db.add(execution)
        
        try:
            await self.db.commit()
            # We successfully inserted the row! We are the sole owner of this execution.
        except (IntegrityError, InvalidRequestError):
            await self.db.rollback()
            # A concurrent request with the SAME idempotency_key beat us to the insert.
            # We fetch and return it without executing.
            import asyncio
            for _ in range(3):
                stmt_conflict = select(ActionExecution).options(selectinload(ActionExecution.attempts)).where(ActionExecution.idempotency_key == idempotency_key)
                conflict_ex = (await self.db.execute(stmt_conflict)).scalar_one_or_none()
                if conflict_ex:
                    return conflict_ex
                await asyncio.sleep(0.05)
            raise ExecutionError(f"Failed to resolve execution for key {idempotency_key} due to concurrency.")
            
        # 5. Mark as RUNNING and create attempt
        # (Since we are the owner, it's safe to proceed)
        execution.status = ActionExecutionStatus.RUNNING
        execution.started_at = datetime.now(timezone.utc).replace(tzinfo=None)
        
        attempt_id = str(uuid.uuid4())
        attempt = ActionExecutionAttempt(
            id=attempt_id,
            action_execution_id=execution.id,
            attempt_number=1,
            status=ActionExecutionStatus.RUNNING
        )
        self.db.add(attempt)
        await self.db.commit()
        
        await action_execution_started(self.db, actor_id=actor_id, execution_id=execution.id)
        
        # 6. Invoke Adapter
        try:
            # We don't hold the DB transaction open during external execution!
            result = await self.adapter.execute(action_request, idempotency_key)
            
            # 7. Handle Result
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
            
            if result.status == ActionExecutionStatus.SUCCEEDED:
                await action_execution_succeeded(self.db, actor_id=actor_id, execution_id=execution.id)
            elif result.status == ActionExecutionStatus.FAILED:
                await action_execution_failed(self.db, actor_id=actor_id, execution_id=execution.id, error_category=result.error_code or "EXECUTION_FAILURE")
                
            return await self._get_execution(execution.id)
            
        except Exception as e:
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
            await action_execution_failed(self.db, actor_id=actor_id, execution_id=execution.id, error_category="UNEXPECTED_ERROR")
            return await self._get_execution(execution.id)

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
