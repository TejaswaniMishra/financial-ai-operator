from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Any

from sqlalchemy import String, ForeignKey, Numeric, DateTime, UniqueConstraint, Enum as SQLEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin
from packages.schemas.reconciliation import (
    ReconciliationRunStatus,
    RelationshipStatus,
    FinancialEvaluationStatus,
    DiscrepancyType,
    Severity,
)

class ReconciliationRun(Base, TimestampMixin):
    __tablename__ = "reconciliation_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[ReconciliationRunStatus] = mapped_column(SQLEnum(ReconciliationRunStatus), default=ReconciliationRunStatus.RUNNING)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    total_records_processed: Mapped[int] = mapped_column(default=0)
    matches_created: Mapped[int] = mapped_column(default=0)
    discrepancies_found: Mapped[int] = mapped_column(default=0)
    
    relationships = relationship("ReconciliationRelationship", back_populates="run", cascade="all, delete-orphan")
    discrepancies = relationship("Discrepancy", back_populates="run", cascade="all, delete-orphan")


class ReconciliationRelationship(Base, TimestampMixin):
    __tablename__ = "reconciliation_relationships"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String, ForeignKey("reconciliation_runs.id"), nullable=False)
    
    source_entity_type: Mapped[str] = mapped_column(String, nullable=False)  # e.g., "PAYMENT", "SETTLEMENT"
    source_entity_id: Mapped[str] = mapped_column(String, nullable=False)
    
    target_entity_type: Mapped[str] = mapped_column(String, nullable=False)  # e.g., "SETTLEMENT", "BANK_TRANSACTION"
    target_entity_id: Mapped[str] = mapped_column(String, nullable=False)
    
    relationship_type: Mapped[str] = mapped_column(String, nullable=False)   # e.g., "PAYMENT_TO_SETTLEMENT"
    
    relationship_status: Mapped[RelationshipStatus] = mapped_column(SQLEnum(RelationshipStatus), nullable=False)
    financial_status: Mapped[FinancialEvaluationStatus] = mapped_column(SQLEnum(FinancialEvaluationStatus), nullable=False)
    
    # Structured deterministic evidence
    evidence: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    run = relationship("ReconciliationRun", back_populates="relationships")

    __table_args__ = (
        UniqueConstraint(
            "source_entity_type",
            "source_entity_id",
            "target_entity_type",
            "target_entity_id",
            "relationship_type",
            name="uq_reconciliation_relationship"
        ),
    )


class Discrepancy(Base, TimestampMixin):
    __tablename__ = "discrepancies"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String, ForeignKey("reconciliation_runs.id"), nullable=False)
    
    rule_code: Mapped[str] = mapped_column(String, nullable=False)
    discrepancy_type: Mapped[DiscrepancyType] = mapped_column(SQLEnum(DiscrepancyType), nullable=False)
    severity: Mapped[Severity] = mapped_column(SQLEnum(Severity), nullable=False)
    
    source_entity_type: Mapped[str] = mapped_column(String, nullable=False)
    source_entity_id: Mapped[str] = mapped_column(String, nullable=False)
    
    related_entity_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    related_entity_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    expected_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4), nullable=True)
    actual_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4), nullable=True)
    difference_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 4), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    
    run = relationship("ReconciliationRun", back_populates="discrepancies")
