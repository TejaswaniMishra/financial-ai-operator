from sqlalchemy import String, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin


class IngestionRecord(Base, TimestampMixin):
    """
    Handles global ingestion idempotency and stores raw payload provenance.
    Prevents duplicate ingestion at the earliest possible stage.
    """
    __tablename__ = "ingestion_records"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", "entity_type", name="uq_ingest_prov_ext_type"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    entity_type: Mapped[str] = mapped_column(String, nullable=False) # e.g. PAYMENT, SETTLEMENT
    
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    
    status: Mapped[str] = mapped_column(String, nullable=False) # PROCESSED, EXCEPTION

    exceptions: Mapped[list["IngestionException"]] = relationship("IngestionException", back_populates="ingestion_record")


class IngestionException(Base, TimestampMixin):
    """
    Captures orphaned records or validation failures without polluting domain tables.
    """
    __tablename__ = "ingestion_exceptions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    ingestion_record_id: Mapped[str] = mapped_column(ForeignKey("ingestion_records.id"), nullable=False)
    error_message: Mapped[str] = mapped_column(String, nullable=False)

    ingestion_record: Mapped["IngestionRecord"] = relationship("IngestionRecord", back_populates="exceptions")
