from datetime import datetime
from sqlalchemy import String, DateTime, JSON, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, Any

from database.base import Base, TimestampMixin

class FinancialPeriod(Base, TimestampMixin):
    __tablename__ = "financial_periods"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    period_name: Mapped[str] = mapped_column(String, nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False) # OPEN, CLOSING, CLOSED
    
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    evaluations: Mapped[list["PeriodCloseEvaluation"]] = relationship(
        "PeriodCloseEvaluation",
        back_populates="period",
        cascade="all, delete-orphan",
        order_by="desc(PeriodCloseEvaluation.evaluated_at)"
    )

class PeriodCloseEvaluation(Base, TimestampMixin):
    __tablename__ = "period_close_evaluations"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    period_id: Mapped[str] = mapped_column(ForeignKey("financial_periods.id"), nullable=False)
    
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evaluated_by: Mapped[str] = mapped_column(String, nullable=False)
    
    is_ready: Mapped[bool] = mapped_column(nullable=False)
    blocking_count: Mapped[int] = mapped_column(nullable=False, default=0)
    warning_count: Mapped[int] = mapped_column(nullable=False, default=0)
    
    control_results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    metrics_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    
    period: Mapped["FinancialPeriod"] = relationship("FinancialPeriod", back_populates="evaluations")
