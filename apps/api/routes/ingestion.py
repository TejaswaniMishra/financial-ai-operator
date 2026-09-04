"""M13 — Ingestion runs REST API.

Durable, idempotent ingestion of external financial source batches into the
authoritative financial domain. Every endpoint is authenticated and gated by
the central RBAC vocabulary:

- VIEW_INGESTION  → list / detail / row-level errors
- INGEST_DATA     → create a run / retry a run

All validation, normalization, deduplication and materialization happens
server-side; these endpoints only marshal safe wire shapes (raw source
payloads are never exposed in responses).
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import get_current_user
from apps.api.authorization import require_permission
from apps.api.dependencies import get_db_session
from database.models.identity import User
from packages.rbac.permissions import Permission
from packages.schemas.ingestion import (
    IngestionRunCreate,
    IngestionRunCreateResponse,
    IngestionRunDetailResponse,
    IngestionRunErrorListResponse,
    IngestionRunListResponse,
    IngestionRunRecordSchema,
    IngestionRetryResponse,
)
from services.ingestion.batch import (
    NothingToRetryError,
    RunNotFoundError,
    create_run,
    get_run,
    list_run_errors,
    list_runs,
    retry_run,
)

router = APIRouter(
    prefix="/ingestion/runs",
    tags=["Ingestion"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "",
    response_model=IngestionRunCreateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(Permission.INGEST_DATA))],
    summary="Ingest one logical source batch",
)
async def create_ingestion_run(
    payload: IngestionRunCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Create + synchronously process one ingestion run.

    Deterministic: valid rows are materialized into the financial domain,
    invalid rows become REJECTED (row-level, never aborting the batch), and
    duplicated logical rows are counted as DUPLICATE. Submitting an identical
    logical batch again returns the existing run with `duplicate=True` and
    creates no new financial facts.
    """
    summary, duplicate = await create_run(
        db,
        source_type=payload.source_type.value,
        source_name=payload.source_name,
        records=payload.records,
        actor_id=current_user.id,
    )
    return IngestionRunCreateResponse(run=summary, duplicate=duplicate)


@router.get(
    "",
    response_model=IngestionRunListResponse,
    dependencies=[Depends(require_permission(Permission.VIEW_INGESTION))],
    summary="List ingestion runs",
)
async def list_ingestion_runs(
    db: AsyncSession = Depends(get_db_session),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by run status"),
):
    result = await list_runs(db, limit=limit, offset=offset, status_filter=status_filter)
    return IngestionRunListResponse(**result)


@router.get(
    "/{run_id}",
    response_model=IngestionRunDetailResponse,
    dependencies=[Depends(require_permission(Permission.VIEW_INGESTION))],
    summary="Get one ingestion run",
)
async def get_ingestion_run(
    run_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    result = await get_run(db, run_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="ingestion run not found"
        )
    return IngestionRunDetailResponse(**result)


@router.get(
    "/{run_id}/errors",
    response_model=IngestionRunErrorListResponse,
    dependencies=[Depends(require_permission(Permission.VIEW_INGESTION))],
    summary="List row-level errors of one ingestion run",
)
async def get_ingestion_run_errors(
    run_id: str,
    db: AsyncSession = Depends(get_db_session),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    result = await list_run_errors(db, run_id, limit=limit, offset=offset)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="ingestion run not found"
        )
    items: List[IngestionRunRecordSchema] = [
        IngestionRunRecordSchema.model_validate(row) for row in result["items"]
    ]
    return IngestionRunErrorListResponse(items=items, total=result["total"])


@router.post(
    "/{run_id}/retry",
    response_model=IngestionRetryResponse,
    dependencies=[Depends(require_permission(Permission.INGEST_DATA))],
    summary="Retry FAILED rows of an ingestion run in a new run",
)
async def retry_ingestion_run(
    run_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Reprocess the FAILED rows of a run as a NEW run.

    Rows already ACCEPTED are never reprocessed — database uniqueness and
    row fingerprints make the retry idempotent, so a retry can never create
    duplicate financial facts.
    """
    try:
        summary, retried_count = await retry_run(
            db, run_id, actor_id=current_user.id
        )
    except RunNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="ingestion run not found"
        )
    except NothingToRetryError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="no failed records to retry in this run",
        )
    return IngestionRetryResponse(run=summary, retried_count=retried_count)