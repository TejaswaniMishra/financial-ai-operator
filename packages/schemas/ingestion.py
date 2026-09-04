"""M13 — Ingestion run & row-level reliability schemas.

Strict typed contracts for the durable ingestion workspace. The backend
owns all validation, normalization, idempotency and materialization; these
models only describe safe wire shapes. Raw source payloads are NEVER exposed
by these response models (raw provenance is stored internally for audit).
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from packages.schemas.enums import (
    IngestionRunRecordStatus,
    IngestionRunStatus,
    IngestionSourceType,
)

# Maximum rows accepted per ingestion run (bounded; documented in M13 doc).
MAX_RECORDS_PER_RUN = 5000
MAX_SOURCE_NAME_LENGTH = 255


class IngestionRunCreate(BaseModel):
    """Request to import one logical source batch.

    `records` are raw source rows (e.g. CSV lines / API objects). Row-level
    validity is decided deterministically by the backend per entity_type;
    malformed rows become row-level REJECTED results, they never abort the
    batch and never reach the financial domain.
    """

    source_type: IngestionSourceType = Field(
        default=IngestionSourceType.MOCK,
        description="Origin of the batch (MOCK/API/CSV).",
    )
    source_name: str = Field(
        ...,
        min_length=1,
        max_length=MAX_SOURCE_NAME_LENGTH,
        description="Human-readable logical label for the batch (e.g. a file name).",
    )
    records: list[dict[str, Any]] = Field(
        ...,
        min_length=1,
        max_length=MAX_RECORDS_PER_RUN,
        description="Raw source records to ingest (1..5000).",
    )

    @field_validator("source_name")
    @classmethod
    def _source_name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("source_name must not be blank")
        return v.strip()

    @field_validator("records")
    @classmethod
    def _records_are_safe_dicts(cls, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for i, row in enumerate(records):
            if not row:
                raise ValueError(f"records[{i}] must be a non-empty object")
            for key, value in row.items():
                if not isinstance(key, str) or not key.strip():
                    raise ValueError(f"records[{i}] contains a non-string field name")
                if value is None:
                    continue
                if not isinstance(value, (str, int, bool, float, list, dict)):
                    raise ValueError(
                        f"records[{i}].{key} has unsupported type {type(value).__name__}"
                    )
        return records


class IngestionRunSummary(BaseModel):
    """One ingestion run as returned by list/detail/create endpoints."""

    id: str
    source_type: str
    source_name: str
    status: IngestionRunStatus
    total_records: int = 0
    successful_records: int = 0
    duplicate_records: int = 0
    rejected_records: int = 0
    failed_records: int = 0
    error_summary: Optional[str] = None
    created_by: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class IngestionRunCreateResponse(BaseModel):
    """Result of POST /ingestion/runs.

    `duplicate` is True when an identical logical batch (same batch
    fingerprint) already exists — the returned run is the existing one and
    no new financial facts were created.
    """

    run: IngestionRunSummary
    duplicate: bool = False


class IngestionRunRecordSchema(BaseModel):
    """Row-level outcome inside a run (raw payload intentionally excluded)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    row_index: int
    entity_type: str
    provider: str
    external_id: str
    status: IngestionRunRecordStatus
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class RunStatusSummary(BaseModel):
    """Aggregate run counts by status for the workspace overview."""

    PENDING: int = 0
    RUNNING: int = 0
    COMPLETED: int = 0
    COMPLETED_WITH_ERRORS: int = 0
    FAILED: int = 0
    total: int = 0
    # Aggregate row-level volume across all runs (real backend counts):
    records_accepted: int = 0
    records_duplicate: int = 0
    records_rejected: int = 0
    records_failed: int = 0


class IngestionRunListResponse(BaseModel):
    items: list[IngestionRunSummary]
    total: int
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    summary: RunStatusSummary


class IngestionRunDetailResponse(BaseModel):
    """Run detail: run summary + authoritative per-status record counts."""

    run: IngestionRunSummary
    record_summary: dict[str, int] = Field(
        default_factory=lambda: {s.value: 0 for s in IngestionRunRecordStatus}
    )


class IngestionRunErrorListResponse(BaseModel):
    """Row-level errors (REJECTED / FAILED) for GET /runs/{id}/errors."""

    items: list[IngestionRunRecordSchema]
    total: int


class IngestionRetryResponse(BaseModel):
    """Result of POST /runs/{id}/retry.

    A NEW run is created containing only the FAILED rows of the source run.
    Rows that were already ACCEPTED are never reprocessed (DB uniqueness +
    fingerprints make the retry idempotent).
    """

    run: IngestionRunSummary
    retried_count: int
