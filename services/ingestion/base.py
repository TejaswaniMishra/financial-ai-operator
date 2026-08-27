import hashlib
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from database.models.ingestion import IngestionRecord, IngestionException


def generate_fingerprint(payload: dict) -> str:
    """
    Generates a deterministic SHA-256 fingerprint for a JSON-serializable payload.
    """
    # Sort keys to ensure deterministic serialization
    serialized = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


class IngestionService:
    """
    Base service for deterministic ingestion of financial records.
    Provides methods to check for idempotency, record ingestion exceptions,
    and manage ingestion records.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_existing_record_by_fingerprint(self, fingerprint: str) -> Optional[IngestionRecord]:
        stmt = select(IngestionRecord).where(IngestionRecord.fingerprint == fingerprint)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_existing_record_by_provider_ext_id(
        self, provider: str, external_id: str, entity_type: str
    ) -> Optional[IngestionRecord]:
        stmt = select(IngestionRecord).where(
            IngestionRecord.provider == provider,
            IngestionRecord.external_id == external_id,
            IngestionRecord.entity_type == entity_type
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_ingestion_record(
        self,
        record_id: str,
        provider: str,
        external_id: str,
        entity_type: str,
        raw_payload: dict,
        status: str = "PROCESSED"
    ) -> IngestionRecord:
        fingerprint = generate_fingerprint(raw_payload)
        record = IngestionRecord(
            id=record_id,
            provider=provider,
            external_id=external_id,
            entity_type=entity_type,
            raw_payload=raw_payload,
            fingerprint=fingerprint,
            status=status
        )
        self.session.add(record)
        return record

    async def create_ingestion_exception(
        self, exception_id: str, ingestion_record_id: str, error_message: str
    ) -> IngestionException:
        exception = IngestionException(
            id=exception_id,
            ingestion_record_id=ingestion_record_id,
            error_message=error_message
        )
        self.session.add(exception)
        
        # Mark the ingestion record as an EXCEPTION
        stmt = select(IngestionRecord).where(IngestionRecord.id == ingestion_record_id)
        result = await self.session.execute(stmt)
        record = result.scalar_one_or_none()
        if record:
            record.status = "EXCEPTION"
            
        return exception
