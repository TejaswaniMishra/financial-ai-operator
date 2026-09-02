from datetime import datetime, timezone
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError

from database.models.action_request import ActionRequest, ActionRequestAudit, ActionRequestStatus
from database.models.policy import PolicyEvaluation, PolicyDecision
from services.action_request.state_machine import ActionRequestStateMachine

class ActionRequestService:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get_request(self, request_id: str) -> ActionRequest:
        stmt = select(ActionRequest).where(ActionRequest.id == request_id)
        request = (await self.db.execute(stmt)).scalar_one_or_none()
        if not request:
            raise ValueError(f"ActionRequest {request_id} not found")
        return request

    async def create_from_evaluation(self, policy_evaluation_id: str, requested_source: str = None) -> ActionRequest:
        """
        Idempotently create an ActionRequest from an APPROVAL_REQUIRED PolicyEvaluation.
        """
        # 1. Load authoritative evaluation
        stmt = select(PolicyEvaluation).where(PolicyEvaluation.id == policy_evaluation_id)
        evaluation = (await self.db.execute(stmt)).scalar_one_or_none()
        
        if not evaluation:
            raise ValueError(f"PolicyEvaluation {policy_evaluation_id} not found")
            
        if evaluation.decision != PolicyDecision.APPROVAL_REQUIRED:
            raise ValueError(f"ActionRequest creation rejected. Policy decision must be APPROVAL_REQUIRED. Got {evaluation.decision.value}")
            
        # 2. Idempotency Check (Service Layer)
        stmt = select(ActionRequest).where(ActionRequest.policy_evaluation_id == policy_evaluation_id)
        existing_request = (await self.db.execute(stmt)).scalar_one_or_none()
        if existing_request:
            return existing_request
            
        # 3. Create the request
        request = ActionRequest(
            investigation_id=evaluation.investigation_id,
            discrepancy_id=evaluation.discrepancy_id,
            policy_evaluation_id=evaluation.id,
            action=evaluation.action.value,
            status=ActionRequestStatus.PENDING_APPROVAL,
            requested_source=requested_source
        )
        
        self.db.add(request)
        
        from sqlalchemy.exc import IntegrityError, InvalidRequestError
        try:
            await self.db.commit()
            await self.db.refresh(request)
            return request
        except (IntegrityError, InvalidRequestError):
            await self.db.rollback()
            # If we hit an IntegrityError (e.g. concurrent creation for the unique policy_evaluation_id constraint),
            # the concurrent transaction might not have committed yet. We retry the read briefly.
            import asyncio
            for _ in range(3):
                existing_request = (await self.db.execute(stmt)).scalar_one_or_none()
                if existing_request:
                    return existing_request
                await asyncio.sleep(0.05)
            raise ValueError(f"ActionRequest for PolicyEvaluation {policy_evaluation_id} could not be created or retrieved due to concurrent modification.")

    async def _transition_state(
        self, 
        request_id: str, 
        new_status: ActionRequestStatus, 
        actor: str = None, 
        reason: str = None
    ) -> ActionRequest:
        """Internal helper to securely transition states and record audit logs."""
        request = await self.get_request(request_id)
        
        # Pure Python state machine validation
        ActionRequestStateMachine.validate_transition(request.status, new_status)
        
        old_status = request.status
        request.status = new_status
        
        # Create audit record
        audit = ActionRequestAudit(
            action_request_id=request.id,
            previous_status=old_status,
            new_status=new_status,
            actor=actor,
            reason=reason
        )
        self.db.add(audit)
        
        await self.db.commit()
        await self.db.refresh(request)
        return request

    async def approve_action_request(self, request_id: str, actor: str = None) -> ActionRequest:
        request = await self._transition_state(request_id, ActionRequestStatus.APPROVED, actor=actor)
        request.approved_by = actor
        request.approved_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await self.db.commit()
        await self.db.refresh(request)
        return request

    async def reject_action_request(self, request_id: str, reason: str = None, actor: str = None) -> ActionRequest:
        request = await self._transition_state(request_id, ActionRequestStatus.REJECTED, actor=actor, reason=reason)
        request.rejection_reason = reason
        await self.db.commit()
        await self.db.refresh(request)
        return request

    async def cancel_action_request(self, request_id: str, reason: str = None, actor: str = None) -> ActionRequest:
        request = await self._transition_state(request_id, ActionRequestStatus.CANCELLED, actor=actor, reason=reason)
        await self.db.commit()
        await self.db.refresh(request)
        return request
