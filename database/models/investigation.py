import uuid
from datetime import datetime, timezone
import enum

from sqlalchemy import Column, String, ForeignKey, DateTime, Boolean, Enum
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship

from database.base import Base

class InvestigationStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"

class RootCauseEnum(str, enum.Enum):
    UNEXPECTED_FEE = "UNEXPECTED_FEE"
    TIMING_DELAY = "TIMING_DELAY"
    DATA_INGESTION_ERROR = "DATA_INGESTION_ERROR"
    CURRENCY_FX_RATE_MISMATCH = "CURRENCY_FX_RATE_MISMATCH"
    SYSTEMIC_PROVIDER_ISSUE = "SYSTEMIC_PROVIDER_ISSUE"
    MISSING_TRANSACTION = "MISSING_TRANSACTION"
    DUPLICATE_TRANSACTION = "DUPLICATE_TRANSACTION"
    PROVIDER_CONFIGURATION_ERROR = "PROVIDER_CONFIGURATION_ERROR"
    RECONCILIATION_RULE_ERROR = "RECONCILIATION_RULE_ERROR"
    UNKNOWN = "UNKNOWN"

class Investigation(Base):
    __tablename__ = "investigation"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    discrepancy_id = Column(String(36), ForeignKey("discrepancies.id"), unique=True, nullable=False)
    status = Column(Enum(InvestigationStatus), default=InvestigationStatus.PENDING, nullable=False)
    active_attempt_id = Column(String(36), ForeignKey("investigation_attempt.id", use_alter=True), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    discrepancy = relationship("Discrepancy", foreign_keys=[discrepancy_id], backref="investigation")
    active_attempt = relationship("InvestigationAttempt", foreign_keys=[active_attempt_id], post_update=True)
    attempts = relationship("InvestigationAttempt", foreign_keys="[InvestigationAttempt.investigation_id]", back_populates="investigation")

class InvestigationAttempt(Base):
    __tablename__ = "investigation_attempt"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    investigation_id = Column(String(36), ForeignKey("investigation.id"), nullable=False)
    
    prompt_version = Column(String(255), nullable=False)
    model_used = Column(String(255), nullable=False)
    context_snapshot = Column(JSON, nullable=False)
    context_hash = Column(String(64), nullable=False)
    raw_llm_response = Column(String, nullable=True)
    
    validated_output = Column(JSON, nullable=True)
    is_valid = Column(Boolean, nullable=False, default=False)
    validation_errors = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    investigation = relationship("Investigation", foreign_keys=[investigation_id], back_populates="attempts")
