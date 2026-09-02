import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import Column, String, ForeignKey, DateTime, Enum, JSON
from sqlalchemy.orm import relationship

from database.base import Base

class ActionRequestStatus(str, enum.Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"

class ActionRequest(Base):
    __tablename__ = "action_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    investigation_id = Column(String(36), ForeignKey("investigation.id"), nullable=False)
    discrepancy_id = Column(String(36), ForeignKey("discrepancies.id"), nullable=True)
    policy_evaluation_id = Column(String(36), ForeignKey("policy_evaluation.id"), nullable=False, unique=True)
    
    action = Column(String, nullable=False)
    status = Column(Enum(ActionRequestStatus), nullable=False, default=ActionRequestStatus.PENDING_APPROVAL)
    
    requested_source = Column(String, nullable=True)
    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    investigation = relationship("Investigation")
    discrepancy = relationship("Discrepancy")
    policy_evaluation = relationship("PolicyEvaluation")


class ActionRequestAudit(Base):
    __tablename__ = "action_request_audits"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action_request_id = Column(String(36), ForeignKey("action_requests.id"), nullable=False)
    
    previous_status = Column(Enum(ActionRequestStatus), nullable=True)
    new_status = Column(Enum(ActionRequestStatus), nullable=False)
    
    actor = Column(String, nullable=True)
    reason = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    action_request = relationship("ActionRequest", backref="audits")
