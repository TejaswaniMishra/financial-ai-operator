from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database.models.policy import PolicyAction, PolicyDecision, PolicyEvaluation
from database.models.investigation import Investigation

class PolicyEngine:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def evaluate(self, investigation_id: str, action: PolicyAction) -> PolicyEvaluation:
        # Load authoritative context
        stmt = select(Investigation).where(Investigation.id == investigation_id)
        investigation = (await self.db.execute(stmt)).scalar_one_or_none()
        
        if not investigation:
            raise ValueError(f"Investigation {investigation_id} not found")

        # Deterministic Policy Rules
        if action == PolicyAction.REQUEST_MANUAL_REVIEW:
            decision = PolicyDecision.ALLOWED
            rule_code = "POLICY_MANUAL_REVIEW_ALLOWED"
            reason = "Manual review is always allowed."
            approval_required = False

        elif action == PolicyAction.RETRY_INVESTIGATION:
            decision = PolicyDecision.ALLOWED
            rule_code = "POLICY_RETRY_ALLOWED"
            reason = "Retrying investigations is allowed."
            approval_required = False

        elif action == PolicyAction.RESOLVE_DISCREPANCY:
            decision = PolicyDecision.APPROVAL_REQUIRED
            rule_code = "POLICY_RESOLUTION_REQUIRES_APPROVAL"
            reason = "Financial resolutions require human approval."
            approval_required = True

        elif action == PolicyAction.REJECT_RECOMMENDATION:
            decision = PolicyDecision.APPROVAL_REQUIRED
            rule_code = "POLICY_REJECTION_REQUIRES_APPROVAL"
            reason = "Rejecting a recommendation requires approval tracking."
            approval_required = True

        elif action == PolicyAction.ESCALATE:
            decision = PolicyDecision.APPROVAL_REQUIRED
            rule_code = "POLICY_ESCALATION_REQUIRES_APPROVAL"
            reason = "Escalations require explicit approval."
            approval_required = True

        else:
            decision = PolicyDecision.DENIED
            rule_code = "POLICY_ACTION_UNSUPPORTED"
            reason = f"The requested action '{action}' is not supported."
            approval_required = False

        # Idempotency check:
        # Prevent uncontrolled duplicate policy decisions for the exact same request.
        stmt = select(PolicyEvaluation).where(
            PolicyEvaluation.investigation_id == investigation_id,
            PolicyEvaluation.action == action
        ).order_by(PolicyEvaluation.created_at.desc()).limit(1)
        
        existing = (await self.db.execute(stmt)).scalar_one_or_none()
        
        # If an identical decision already exists, return it instead of duplicating.
        # This handles UI retries/spam clicks cleanly.
        if existing and existing.decision == decision and existing.rule_code == rule_code:
            return existing

        evaluation = PolicyEvaluation(
            investigation_id=investigation_id,
            discrepancy_id=investigation.discrepancy_id,
            action=action,
            decision=decision,
            rule_code=rule_code,
            reason=reason,
            approval_required=approval_required
        )
        self.db.add(evaluation)
        await self.db.commit()
        await self.db.refresh(evaluation)
        return evaluation
