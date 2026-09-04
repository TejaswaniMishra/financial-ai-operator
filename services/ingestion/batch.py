"""M13 — Ingestion run lifecycle (durable, idempotent, retryable).

One run = one logical source batch. Invariants enforced here (with the
database as the final authority):

1. batch fingerprint UNIQUE → the same logical batch can never create two
   runs, even when two submissions race (IntegrityError on the unique index
   is caught and resolved to the existing run).
2. Row identity (provider + external_id + entity_type) and row fingerprint
   are checked before materialization, and the IngestionRecord fingerprint /
   provider-ext-entity plus domain unique constraints backstop every accept,
   so retries can never duplicate an already accepted fact.
3. Each row is persisted as FAILED *before* its materialization attempt and
   updated to its real outcome inside a SAVEPOINT — an unexpected mid-batch
   failure therefore never loses audit rows and every FAILED row is retryable.
4. Partial failure never rolls back accepted rows (documented atomicity:
   row-granular, not batch-granular).
"""

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.ingestion import IngestionRecord, IngestionRun, IngestionRunRecord
from packages.schemas.enums import (
    IngestionRunRecordStatus,
    IngestionRunStatus,
    IngestionSourceType,
)
from packages.schemas.ingestion import (
    IngestionRunSummary,
    RunStatusSummary,
    MAX_SOURCE_NAME_LENGTH,
)
from services.auth.security_events import (
    ingestion_completed,
    ingestion_failed,
    ingestion_started,
)
from services.ingestion.base import generate_fingerprint
from services.ingestion.materialize import (
    MaterializationError,
    materialize_domain_fact,
)
from services.ingestion.validation import (
    normalize_row,
    new_run_id,
    new_run_record_id,
)
from services.notifications.service import (
    INGESTION_COMPLETED_WITH_ERRORS,
    INGESTION_FAILED as NOTIFICATION_INGESTION_FAILED,
    notify_user,
)

MAX_RETRY_RECORDS = 5000


class RunNotFoundError(Exception):
    pass


class NothingToRetryError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _batch_fingerprint(source_type: str, row_fingerprints: list[str]) -> str:
    """Deterministic fingerprint of the logical batch.

    Ordering of rows does not change the batch identity (sorted fingerprints),
    so an identical logical payload submitted in any row order is one run.
    """
    return generate_fingerprint(
        {"source_type": source_type, "rows": sorted(row_fingerprints)}
    )


def _identity_from_raw(raw: dict) -> tuple[str, str, str]:
    """Best-effort row identity for audit rows (invalid rows included)."""
    entity_type = str(raw.get("entity_type", "UNKNOWN"))[:32] or "UNKNOWN"
    provider = str(raw.get("provider", ""))[:64]
    external_id = str(raw.get("external_id", ""))[:255]
    return entity_type.upper() if entity_type != "UNKNOWN" else entity_type, provider, external_id


async def _find_existing_record(db: AsyncSession, entity_type: str, provider: str, external_id: str) -> Optional[IngestionRecord]:
    stmt = select(IngestionRecord).where(
        IngestionRecord.entity_type == entity_type,
        IngestionRecord.provider == provider,
        IngestionRecord.external_id == external_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _run_summary(run: IngestionRun) -> IngestionRunSummary:
    return IngestionRunSummary(
        id=run.id,
        source_type=run.source_type,
        source_name=run.source_name,
        status=IngestionRunStatus(run.status),
        total_records=run.total_records,
        successful_records=run.successful_records,
        duplicate_records=run.duplicate_records,
        rejected_records=run.rejected_records,
        failed_records=run.failed_records,
        error_summary=run.error_summary,
        created_by=run.created_by,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def _status_value(status: IngestionRunRecordStatus) -> str:
    return status.value


async def _process_rows(
    db: AsyncSession,
    run: IngestionRun,
    normalized_rows: list,
) -> list[tuple[IngestionRunRecord, IngestionRunRecordStatus, Optional[str], Optional[str]]]:
    """Persist one IngestionRunRecord per source row and materialize valid rows.

    Each row record is flushed as FAILED *before* its materialization attempt
    and updated to its real outcome inside a SAVEPOINT, so an unexpected
    mid-batch failure can never lose the audit trail.
    """
    outcome_by_record: list[tuple[IngestionRunRecord, IngestionRunRecordStatus, Optional[str], Optional[str]]] = []
    for i, norm in enumerate(normalized_rows):
        entity_type, provider, external_id = _identity_from_raw(norm.raw_payload)
        record = IngestionRunRecord(
            id=new_run_record_id(),
            run_id=run.id,
            row_index=i,
            entity_type=entity_type,
            provider=provider,
            external_id=external_id,
            row_fingerprint=(
                norm.row_fingerprint if norm.valid else generate_fingerprint(norm.raw_payload)
            ),
            status=_status_value(IngestionRunRecordStatus.FAILED),
            raw_payload=norm.raw_payload,
        )
        db.add(record)
        await db.flush()

        if not norm.valid:
            record.status = _status_value(IngestionRunRecordStatus.REJECTED)
            record.error_code = norm.error_code
            record.error_message = norm.error_message[:1000]
            outcome_by_record.append((record, IngestionRunRecordStatus.REJECTED, norm.error_code, norm.error_message))
            continue

        # Fast-path duplicate check (database constraints are the backstop).
        existing = await _find_existing_record(
            db, norm.entity_type, norm.provider, norm.external_id
        )
        if existing is not None:
            record.status = _status_value(IngestionRunRecordStatus.DUPLICATE)
            outcome_by_record.append((record, IngestionRunRecordStatus.DUPLICATE, None, None))
            continue

        try:
            async with db.begin_nested():
                await materialize_domain_fact(
                    db,
                    run_id=run.id,
                    entity_type=norm.entity_type,
                    payload=norm.payload,
                    raw=norm.raw_payload,
                    row_fingerprint=norm.row_fingerprint,
                )
                await db.flush()
            record.status = _status_value(IngestionRunRecordStatus.ACCEPTED)
            outcome_by_record.append((record, IngestionRunRecordStatus.ACCEPTED, None, None))
        except IntegrityError:
            # Race lost: the same source fact was inserted concurrently.
            # Classify as DUPLICATE only if the fact now exists.
            outcome = IngestionRunRecordStatus.DUPLICATE
            code: Optional[str] = None
            message: Optional[str] = None
            recheck = await _find_existing_record(
                db, norm.entity_type, norm.provider, norm.external_id
            )
            if recheck is None:
                outcome = IngestionRunRecordStatus.FAILED
                code = "INTEGRITY_CONFLICT"
                message = "unique constraint conflict while persisting source row"
            record.status = _status_value(outcome)
            record.error_code = code
            record.error_message = message
            outcome_by_record.append((record, outcome, code, message))
        except MaterializationError as exc:
            record.status = _status_value(IngestionRunRecordStatus.REJECTED)
            record.error_code = exc.code
            record.error_message = exc.message[:1000]
            outcome_by_record.append((record, IngestionRunRecordStatus.REJECTED, exc.code, exc.message))

    return outcome_by_record


async def create_run(
    db: AsyncSession,
    *,
    source_type: str,
    source_name: str,
    records: list[dict],
    actor_id: str,
) -> tuple[IngestionRunSummary, bool]:
    """Create + execute one ingestion run (synchronously, bounded batch).

    Returns (run summary, duplicate). `duplicate=True` means an identical
    logical batch already exists — the returned run is the existing one and
    nothing new was persisted.
    """
    normalized_rows = [normalize_row(raw, i) for i, raw in enumerate(records)]
    valid_fingerprints = [r.row_fingerprint for r in normalized_rows if r.valid]
    batch_fp = _batch_fingerprint(source_type, valid_fingerprints)

    run = IngestionRun(
        id=new_run_id(),
        source_type=source_type,
        source_name=source_name[:MAX_SOURCE_NAME_LENGTH],
        status=IngestionRunStatus.PENDING.value,
        batch_fingerprint=batch_fp,
        total_records=len(records),
        created_by=actor_id,
        started_at=_now(),
    )
    db.add(run)
    try:
        await db.flush()
    except IntegrityError:
        # Concurrent (or repeated) submission of the same logical batch.
        # Resolve to the existing run — no new financial facts are created.
        await db.rollback()
        existing = (
            await db.execute(
                select(IngestionRun).where(IngestionRun.batch_fingerprint == batch_fp)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return await _run_summary(existing), True
        raise  # Unreachable in practice: uniqueness is database-enforced.

    run.status = IngestionRunStatus.RUNNING.value
    await ingestion_started(db, actor_id, run.id)

    try:
        outcome_by_record = await _process_rows(db, run, normalized_rows)
    except Exception:
        # An unexpected mid-batch failure must never lose the audit trail:
        # FAILED row records were flushed before each attempt, so persist the
        # run as FAILED (retryable) and re-raise for the API error path.
        try:
            failed_count = int(
                (
                    await db.execute(
                        select(func.count())
                        .select_from(IngestionRunRecord)
                        .where(
                            IngestionRunRecord.run_id == run.id,
                            IngestionRunRecord.status == IngestionRunRecordStatus.FAILED.value,
                        )
                    )
                ).scalar_one()
            )
            run.status = IngestionRunStatus.FAILED.value
            run.failed_records = failed_count
            run.error_summary = (
                "unexpected batch processing failure; FAILED rows remain retryable"
            )
            run.completed_at = _now()
            await ingestion_failed(db, actor_id, run.id)
            await notify_user(
                db,
                actor_id,
                NOTIFICATION_INGESTION_FAILED,
                "Ingestion batch failed",
                f"Batch '{run.source_name}' failed unexpectedly; {failed_count} row(s) remain retryable.",
                target_type="ingestion_run",
                target_id=run.id,
            )
            await db.commit()
        except Exception:
            await db.rollback()
        raise

    # Finalize run counters + status.
    counters = {s: 0 for s in IngestionRunRecordStatus}
    for _, status, _, _ in outcome_by_record:
        counters[status] += 1
    run.successful_records = counters[IngestionRunRecordStatus.ACCEPTED]
    run.duplicate_records = counters[IngestionRunRecordStatus.DUPLICATE]
    run.rejected_records = counters[IngestionRunRecordStatus.REJECTED]
    run.failed_records = counters[IngestionRunRecordStatus.FAILED]
    run.completed_at = _now()
    run.status = (
        IngestionRunStatus.COMPLETED.value
        if (run.rejected_records + run.failed_records) == 0
        else IngestionRunStatus.COMPLETED_WITH_ERRORS.value
    )
    if (run.rejected_records + run.failed_records) > 0:
        run.error_summary = (
            f"{run.rejected_records} record(s) rejected, "
            f"{run.failed_records} record(s) failed"
        )

    if run.status == IngestionRunStatus.COMPLETED.value:
        await ingestion_completed(db, actor_id, run.id)
    else:
        await ingestion_failed(db, actor_id, run.id)
        await notify_user(
            db,
            actor_id,
            INGESTION_COMPLETED_WITH_ERRORS,
            "Ingestion completed with errors",
            f"Batch '{run.source_name}': {run.successful_records} accepted, "
            f"{run.duplicate_records} duplicate(s), {run.rejected_records} rejected, "
            f"{run.failed_records} failed.",
            target_type="ingestion_run",
            target_id=run.id,
        )

    await db.commit()
    return await _run_summary(run), False


async def list_runs(
    db: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    status_filter: Optional[str] = None,
) -> dict[str, Any]:
    """Paginated run list + deterministic status/volume summary."""
    base = select(IngestionRun)
    if status_filter is not None:
        base = base.where(IngestionRun.status == status_filter)

    total = (
        await db.execute(
            select(func.count()).select_from(base.subquery())
        )
    ).scalar_one()

    rows = (
        await db.execute(
            base.order_by(IngestionRun.created_at.desc(), IngestionRun.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()

    # Summary: run counts by status + aggregate row volume across all runs.
    status_rows = (
        await db.execute(
            select(IngestionRun.status, func.count())
            .group_by(IngestionRun.status)
        )
    ).all()
    volume = (
        await db.execute(
            select(
                func.coalesce(func.sum(IngestionRun.successful_records), 0),
                func.coalesce(func.sum(IngestionRun.duplicate_records), 0),
                func.coalesce(func.sum(IngestionRun.rejected_records), 0),
                func.coalesce(func.sum(IngestionRun.failed_records), 0),
            )
        )
    ).one()

    status_counts = {status: count for status, count in status_rows}
    summary = RunStatusSummary(
        PENDING=status_counts.get(IngestionRunStatus.PENDING.value, 0),
        RUNNING=status_counts.get(IngestionRunStatus.RUNNING.value, 0),
        COMPLETED=status_counts.get(IngestionRunStatus.COMPLETED.value, 0),
        COMPLETED_WITH_ERRORS=status_counts.get(IngestionRunStatus.COMPLETED_WITH_ERRORS.value, 0),
        FAILED=status_counts.get(IngestionRunStatus.FAILED.value, 0),
        total=total,
        records_accepted=int(volume[0]),
        records_duplicate=int(volume[1]),
        records_rejected=int(volume[2]),
        records_failed=int(volume[3]),
    )
    return {
        "items": [await _run_summary(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        "summary": summary,
    }


async def get_run(db: AsyncSession, run_id: str) -> Optional[dict[str, Any]]:
    run = (
        await db.execute(select(IngestionRun).where(IngestionRun.id == run_id))
    ).scalar_one_or_none()
    if run is None:
        return None
    record_rows = (
        await db.execute(
            select(IngestionRunRecord.status, func.count())
            .where(IngestionRunRecord.run_id == run_id)
            .group_by(IngestionRunRecord.status)
        )
    ).all()
    record_summary = {s.value: 0 for s in IngestionRunRecordStatus}
    for status, count in record_rows:
        if status in record_summary:
            record_summary[status] = count
    return {
        "run": await _run_summary(run),
        "record_summary": record_summary,
    }


async def list_run_errors(
    db: AsyncSession,
    run_id: str,
    *,
    limit: int = 100,
    offset: int = 0,
) -> Optional[dict[str, Any]]:
    run = (
        await db.execute(select(IngestionRun).where(IngestionRun.id == run_id))
    ).scalar_one_or_none()
    if run is None:
        return None
    base = select(IngestionRunRecord).where(
        IngestionRunRecord.run_id == run_id,
        IngestionRunRecord.status.in_(
            [
                IngestionRunRecordStatus.REJECTED.value,
                IngestionRunRecordStatus.FAILED.value,
            ]
        ),
    )
    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    rows = (
        await db.execute(
            base.order_by(
                IngestionRunRecord.row_index.asc(),
                IngestionRunRecord.id.asc(),
            )
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()
    return {
        "items": rows,
        "total": total,
    }


async def retry_run(
    db: AsyncSession,
    run_id: str,
    *,
    actor_id: str,
) -> tuple[IngestionRunSummary, int]:
    """Reprocess FAILED rows of a run in a NEW run.

    Already-accepted rows are never reprocessed: the new batch only contains
    the FAILED rows, and even those are re-checked against the database, so a
    retry can never duplicate an accepted financial fact.
    """
    run = (
        await db.execute(select(IngestionRun).where(IngestionRun.id == run_id))
    ).scalar_one_or_none()
    if run is None:
        raise RunNotFoundError(run_id)

    failed_rows = (
        await db.execute(
            select(IngestionRunRecord)
            .where(
                IngestionRunRecord.run_id == run_id,
                IngestionRunRecord.status == IngestionRunRecordStatus.FAILED.value,
            )
            .order_by(IngestionRunRecord.row_index.asc(), IngestionRunRecord.id.asc())
        )
    ).scalars().all()

    if not failed_rows:
        raise NothingToRetryError(run_id)

    retried_payloads = [row.raw_payload or {} for row in failed_rows]
    retry_name = (
        f"retry:{run.id[:12]}:{run.source_name}"[:MAX_SOURCE_NAME_LENGTH]
    )
    summary, _duplicate = await create_run(
        db,
        source_type=run.source_type,
        source_name=retry_name,
        records=retried_payloads,
        actor_id=actor_id,
    )
    return summary, len(retried_payloads)
