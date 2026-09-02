import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import Column, String, ForeignKey, DateTime, Enum, Boolean
from sqlalchemy.orm import relationship

from database.base import Base

class PolicyAction(str, enum.Enum):
    REQUEST_MANUAL_REVIEW = "REQUEST_MANUAL_REVIEW"
    RETRY_INVESTIGATION = "RETRY_INVESTIGATION"
    RESOLVE_DISCREPANCY = "RESOLVE_DISCREPANCY"
    REJECT_RECOMMENDATION = "REJECT_RECOMMENDATION"
    ESCALATE = "ESCALATE"

class PolicyDecision(str, enum.Enum):
    ALLOWED = "ALLOWED"
    DENIED = "DENIED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"

class PolicyEvaluation(Base):
    __tablename__ = "policy_evaluation"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    investigation_id = Column(String(36), ForeignKey("investigation.id"), nullable=False)
    discrepancy_id = Column(String(36), ForeignKey("discrepancies.id"), nullable=True)

    action = Column(Enum(PolicyAction), nullable=False)
    decision = Column(Enum(PolicyDecision), nullable=False)
    rule_code = Column(String(255), nullable=False)
    reason = Column(String, nullable=False)
    approval_required = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    investigation = relationship("Investigation", foreign_keys=[investigation_id])
    discrepancy = relationship("Discrepancy", foreign_keys=[discrepancy_id])
