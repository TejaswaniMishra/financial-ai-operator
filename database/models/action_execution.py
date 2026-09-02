import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import Column, String, ForeignKey, DateTime, Enum, JSON, Integer
from sqlalchemy.orm import relationship

from database.base import Base

class ActionExecutionStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"

class ActionExecution(Base):
    __tablename__ = "action_executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action_request_id = Column(String(36), ForeignKey("action_requests.id"), nullable=False)
    idempotency_key = Column(String(255), nullable=False, unique=True)
    
    status = Column(Enum(ActionExecutionStatus), nullable=False, default=ActionExecutionStatus.PENDING)
    execution_type = Column(String, nullable=False)  # e.g., "simulation", "live"
    adapter = Column(String, nullable=False)         # e.g., "simulator", "stripe", "plaid"
    
    requested_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    result = Column(JSON, nullable=True)
    error_code = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    action_request = relationship("ActionRequest", backref="executions")
    attempts = relationship("ActionExecutionAttempt", back_populates="action_execution", cascade="all, delete-orphan", order_by="ActionExecutionAttempt.attempt_number")


class ActionExecutionAttempt(Base):
    __tablename__ = "action_execution_attempts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action_execution_id = Column(String(36), ForeignKey("action_executions.id"), nullable=False)
    attempt_number = Column(Integer, nullable=False)
    
    status = Column(Enum(ActionExecutionStatus), nullable=False)
    
    started_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    completed_at = Column(DateTime, nullable=True)
    
    result = Column(JSON, nullable=True)
    error_code = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    action_execution = relationship("ActionExecution", back_populates="attempts")
