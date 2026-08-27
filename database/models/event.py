from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Numeric, JSON
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional

from database.base import Base


class FinancialEvent(Base):
    """
    Strictly append-only state transition log.
    Captures significant events in the financial lifecycle.
    """
    __tablename__ = "financial_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    merchant_id: Mapped[str] = mapped_column(String, nullable=False)
    
    entity_type: Mapped[str] = mapped_column(String, nullable=False) # e.g. PAYMENT, SETTLEMENT
    entity_id: Mapped[str] = mapped_column(String, nullable=False)
    
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    
    amount: Mapped[Optional[float]] = mapped_column(Numeric(18, 4), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)
    
    metadata_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        nullable=False
    )
