from typing import Optional
from datetime import datetime

from sqlalchemy import String, ForeignKey, JSON, Integer, UniqueConstraint, Index, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin


class IngestionRun(Base, TimestampMixin):
    """Durable, auditable ingestion batch (M13).

    One run corresponds to one logical source submission. The batch
    fingerprint is UNIQUE at the database level so repeated or concurrent
    submission of the same logical payload cannot create a second run (and
    therefore cannot create duplicate financial facts).
    """

    __tablename__ = "ingestion_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # PENDING / RUNNING / COMPLETED / COMPLETED_WITH_ERRORS / FAILED
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    batch_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    total_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    error_summary: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    # Server-derived actor identity (authenticated user id) — never client input.
    created_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    records: Mapped[list["IngestionRunRecord"]] = relationship(
        "IngestionRunRecord", back_populates="run", cascade="all, delete-orphan"
    )


class IngestionRunRecord(Base, TimestampMixin):
    """Row-level outcome of one source record inside an ingestion run.

    Status is one of ACCEPTED / DUPLICATE / REJECTED / FAILED. Rejected and
    failed rows keep a safe error code/message plus the raw source payload
    (internal audit + retry only — never exposed by API response schemas).
    """

    __tablename__ = "ingestion_run_records"
    __table_args__ = (
        Index("ix_ing_run_rec_run_status", "run_id", "status"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("ingestion_runs.id"), nullable=False, index=True)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)  # PAYMENT, REFUND, ...
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)

    row_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    # ACCEPTED / DUPLICATE / REJECTED / FAILED
    status: Mapped[str] = mapped_column(String(32), nullable=False)

    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    run: Mapped["IngestionRun"] = relationship("IngestionRun", back_populates="records")


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

    # Lineage (M13): the ingestion run that produced this source fact.
    run_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("ingestion_runs.id"), nullable=True, index=True
    )

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
