from typing import Optional, List, Tuple
from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc

from database.models.reconciliation import Discrepancy
from database.models.investigation import Investigation
from database.models.policy import PolicyEvaluation
from database.models.action_request import ActionRequest
from database.models.action_execution import ActionExecution

from packages.schemas.exceptions import ExceptionReadSummary, ExceptionDetail, OverallExceptionState, ExceptionListResponse
from packages.schemas.reconciliation import DiscrepancyType, Severity

def _determine_overall_state(
    inv_status: Optional[str],
    pol_decision: Optional[str],
    req_status: Optional[str],
    exec_status: Optional[str]
) -> OverallExceptionState:
    if exec_status:
        if exec_status == "SUCCEEDED":
            return OverallExceptionState.RESOLVED
        if exec_status == "FAILED":
            return OverallExceptionState.FAILED
        if exec_status == "UNKNOWN":
            return OverallExceptionState.UNKNOWN
        if exec_status in ["PENDING", "RUNNING"]:
            return OverallExceptionState.EXECUTING
            
    if req_status:
        if req_status == "APPROVED":
            return OverallExceptionState.APPROVED
        if req_status == "PENDING_APPROVAL":
            return OverallExceptionState.AWAITING_APPROVAL
        if req_status in ["REJECTED", "CANCELLED"]:
            return OverallExceptionState.OPEN

    if pol_decision:
        if pol_decision == "DENIED":
            return OverallExceptionState.RESOLVED
        if pol_decision == "APPROVAL_REQUIRED":
            return OverallExceptionState.AWAITING_APPROVAL
            
    if inv_status:
        if inv_status == "PENDING":
            return OverallExceptionState.INVESTIGATING
        if inv_status in ["FAILED", "UNAVAILABLE"]:
            return OverallExceptionState.FAILED
            
    return OverallExceptionState.OPEN


from sqlalchemy import case, literal_column

async def list_exceptions(
    session: AsyncSession,
    limit: int = 50,
    offset: int = 0,
    discrepancy_type: Optional[str] = None,
    overall_state: Optional[str] = None,
    currency: Optional[str] = None,
    transaction_type: Optional[str] = None,
) -> ExceptionListResponse:
    
    # We will derive the state in SQL to allow filtering
    exec_status = ActionExecution.status
    req_status = ActionRequest.status
    pol_decision = PolicyEvaluation.decision
    inv_status = Investigation.status
    
    overall_state_case = case(
        (exec_status == "SUCCEEDED", OverallExceptionState.RESOLVED.value),
        (exec_status == "FAILED", OverallExceptionState.FAILED.value),
        (exec_status == "UNKNOWN", OverallExceptionState.UNKNOWN.value),
        (exec_status.in_(["PENDING", "RUNNING"]), OverallExceptionState.EXECUTING.value),
        
        (req_status == "APPROVED", OverallExceptionState.APPROVED.value),
        (req_status == "PENDING_APPROVAL", OverallExceptionState.AWAITING_APPROVAL.value),
        (req_status.in_(["REJECTED", "CANCELLED"]), OverallExceptionState.OPEN.value),
        
        (pol_decision == "DENIED", OverallExceptionState.RESOLVED.value),
        (pol_decision == "APPROVAL_REQUIRED", OverallExceptionState.AWAITING_APPROVAL.value),
        
        (inv_status == "PENDING", OverallExceptionState.INVESTIGATING.value),
        (inv_status.in_(["FAILED", "UNAVAILABLE"]), OverallExceptionState.FAILED.value),
        
        else_=OverallExceptionState.OPEN.value
    )

    base_stmt = select(
        Discrepancy,
        inv_status.label("inv_status"),
        pol_decision.label("pol_decision"),
        req_status.label("req_status"),
        exec_status.label("exec_status")
    ).outerjoin(
        Investigation, Investigation.discrepancy_id == Discrepancy.id
    ).outerjoin(
        PolicyEvaluation, PolicyEvaluation.investigation_id == Investigation.id
    ).outerjoin(
        ActionRequest, ActionRequest.policy_evaluation_id == PolicyEvaluation.id
    ).outerjoin(
        ActionExecution, ActionExecution.action_request_id == ActionRequest.id
    )

    if discrepancy_type:
        base_stmt = base_stmt.where(Discrepancy.discrepancy_type == discrepancy_type)
    if currency:
        base_stmt = base_stmt.where(Discrepancy.currency == currency)
    if transaction_type:
        base_stmt = base_stmt.where(Discrepancy.source_entity_type == transaction_type)
    if overall_state:
        base_stmt = base_stmt.where(overall_state_case == overall_state)
        
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = (await session.execute(count_stmt)).scalar() or 0
    
    stmt = base_stmt.order_by(desc(Discrepancy.created_at)).limit(limit).offset(offset)
    
    result = await session.execute(stmt)
    rows = result.all()
    
    items = []
    for row in rows:
        disc: Discrepancy = row.Discrepancy
        
        inv_st = getattr(row.inv_status, "value", row.inv_status) if row.inv_status else None
        pol_dec = getattr(row.pol_decision, "value", row.pol_decision) if row.pol_decision else None
        req_st = getattr(row.req_status, "value", row.req_status) if row.req_status else None
        exec_st = getattr(row.exec_status, "value", row.exec_status) if row.exec_status else None
        
        computed_state = _determine_overall_state(inv_st, pol_dec, req_st, exec_st)
            
        summary = ExceptionReadSummary(
            id=disc.id,
            type=disc.discrepancy_type,
            severity=disc.severity,
            overall_state=computed_state,
            amount=disc.difference_amount,
            currency=disc.currency,
            source_entity_type=disc.source_entity_type,
            source_entity_id=disc.source_entity_id,
            detected_at=disc.created_at,
            investigation_status=inv_st,
            policy_decision=pol_dec,
            action_request_status=req_st,
            execution_status=exec_st,
        )
        items.append(summary)
        
    return ExceptionListResponse(
        items=items,
        total=total,
        page=offset // limit + 1,
        size=limit
    )


async def get_exception_detail(session: AsyncSession, exception_id: str) -> Optional[ExceptionDetail]:
    # We need to fetch discrepancy and eagerly load all relationships
    from sqlalchemy.orm import selectinload
    
    stmt = (
        select(Discrepancy)
        .where(Discrepancy.id == exception_id)
        .options(
            selectinload(Discrepancy.investigation).selectinload(Investigation.attempts),
        )
    )
    result = await session.execute(stmt)
    disc = result.scalar_one_or_none()
    
    if not disc:
        return None
        
    inv = disc.investigation if disc.investigation else []
    inv = inv[0] if isinstance(inv, list) and len(inv) > 0 else inv # some mappings make it a list
    if not isinstance(inv, Investigation):
        inv = None
        
    # the relationship is uselist=False if it's 1-1, let's check what it is.
    # Assuming it's a list based on relationship("Investigation", foreign_keys=[discrepancy_id], backref="investigation") - actually backref makes it scalar or list? Wait, in models/investigation.py: discrepancy = relationship("Discrepancy", ..., backref="investigation") -> that means discrepancy.investigation is a list.
    if isinstance(inv, list) and len(inv) > 0:
        inv = inv[0]
    elif isinstance(inv, list):
        inv = None
        
    pol_eval = None
    act_req = None
    act_exec = None
    
    if inv:
        # fetch policy evaluation
        pol_stmt = select(PolicyEvaluation).where(PolicyEvaluation.investigation_id == inv.id)
        pol_eval = (await session.execute(pol_stmt)).scalar_one_or_none()
        
        if pol_eval:
            req_stmt = select(ActionRequest).where(ActionRequest.policy_evaluation_id == pol_eval.id)
            act_req = (await session.execute(req_stmt)).scalar_one_or_none()
            
            if act_req:
                exec_stmt = select(ActionExecution).where(ActionExecution.action_request_id == act_req.id).order_by(desc(ActionExecution.created_at))
                act_exec = (await session.execute(exec_stmt)).scalars().first()
                
    # Deriving states
    inv_st = inv.status.value if inv else None
    pol_dec = pol_eval.decision.value if pol_eval else None
    req_st = act_req.status.value if act_req else None
    exec_st = act_exec.status.value if act_exec else None
    
    computed_state = _determine_overall_state(inv_st, pol_dec, req_st, exec_st)
    
    root_cause = None
    explanation = None
    
    if inv:
        # Surface the newest validated attempt's findings. The validated
        # output schema stores root cause under root_cause_category and the
        # narrative under summary (legacy code read non-existent keys).
        for attempt in sorted(inv.attempts, key=lambda a: a.created_at or datetime.min, reverse=True):
            if attempt.is_valid and attempt.validated_output:
                root_cause = attempt.validated_output.get("root_cause_category")
                explanation = attempt.validated_output.get("summary")
                break
                
    return ExceptionDetail(
        id=disc.id,
        type=disc.discrepancy_type,
        severity=disc.severity,
        overall_state=computed_state,
        amount=disc.difference_amount,
        expected_amount=disc.expected_amount,
        actual_amount=disc.actual_amount,
        difference_amount=disc.difference_amount,
        currency=disc.currency,
        source_entity_type=disc.source_entity_type,
        source_entity_id=disc.source_entity_id,
        related_entity_type=disc.related_entity_type,
        related_entity_id=disc.related_entity_id,
        detected_at=disc.created_at,
        run_id=disc.run_id,
        rule_code=disc.rule_code,
        
        investigation_status=inv_st,
        investigation_id=inv.id if inv else None,
        root_cause=root_cause,
        investigation_explanation=explanation,
        
        policy_decision=pol_dec,
        policy_action=pol_eval.action.value if pol_eval else None,
        policy_rule_code=pol_eval.rule_code if pol_eval else None,
        policy_reason=pol_eval.reason if pol_eval else None,
        
        action_request_id=act_req.id if act_req else None,
        action_request_status=req_st,
        action_request_action=act_req.action if act_req else None,
        
        execution_id=act_exec.id if act_exec else None,
        execution_status=exec_st,
        execution_error=act_exec.error_message if act_exec else None,
    )
